/*
 * imgproc.c — PDF Love's native image-processing kernel.
 *
 * The scan-cleanup pipeline that runs before OCR, written as exactly two
 * passes over the pixel data (the theoretical minimum: one to read, one
 * to write):
 *
 *   pass 1  gray_and_hist(): RGB(A) -> grayscale + 256-bin histogram
 *   (host)  build_lut(): contrast stretch + inversion detection + Otsu
 *           threshold, all computed on the histogram — 256 entries, no
 *           pixel access at all
 *   pass 2  apply_lut(): map every pixel through the finished LUT
 *
 * The Python side (native_ops.py) loads this with ctypes and falls back
 * to a pure-Pillow implementation when the shared library isn't present,
 * so the API works either way.
 *
 * Build (done automatically in the Dockerfile):
 *   gcc -O3 -shared -fPIC -o imgproc.so imgproc.c
 */

#include <stdint.h>
#include <stddef.h>

/* Pass 1: luminance (ITU-R BT.601, integer math) of an RGB/RGBA buffer
 * into an 8-bit grayscale buffer, accumulating the histogram in the same
 * sweep. `channels` is 3 or 4; hist must hold 256 uint64 slots (zeroed). */
void gray_and_hist(const uint8_t *src, uint8_t *dst, size_t npixels,
                   int channels, uint64_t *hist)
{
    for (size_t i = 0; i < npixels; i++) {
        const uint8_t *p = src + i * (size_t)channels;
        /* 0.299 R + 0.587 G + 0.114 B, scaled by 1024 */
        uint8_t g = (uint8_t)((306u * p[0] + 601u * p[1] + 117u * p[2]) >> 10);
        dst[i] = g;
        hist[g]++;
    }
}

/* Histogram of an already-grayscale buffer (used for mode-"L" inputs). */
void hist_only(const uint8_t *gray, size_t npixels, uint64_t *hist)
{
    for (size_t i = 0; i < npixels; i++) hist[gray[i]]++;
}

/* Host step, no pixel access: derive the complete cleanup LUT from the
 * histogram. Chains three classic operations:
 *   1. percentile contrast stretch (p_low/p_high are per-mille cutoffs,
 *      e.g. 5 and 995 = clip 0.5% at each end) — lifts faded scans;
 *   2. inversion detection (mean < 100 after stretch = white-on-black
 *      scan, which OCR engines can't read until flipped);
 *   3. Otsu's method for the final binarization threshold.
 * Because each operation is a monotonic (or affine) remap, the whole
 * chain can be computed on the 256-bin histogram and folded into a
 * single 256-byte lookup table. Returns the Otsu threshold in stretched
 * space (useful for diagnostics). */
int build_lut(const uint64_t *hist, size_t npixels, int p_low, int p_high,
              uint8_t *lut /* 256 bytes */)
{
    /* -- 1. stretch bounds from percentiles ------------------------- */
    uint64_t lo_count = (uint64_t)((double)npixels * (double)p_low / 1000.0);
    uint64_t hi_count = (uint64_t)((double)npixels * (double)p_high / 1000.0);
    int lo = 0, hi = 255;
    uint64_t cum = 0;
    for (int v = 0; v < 256; v++) { cum += hist[v]; if (cum > lo_count) { lo = v; break; } }
    cum = 0;
    for (int v = 0; v < 256; v++) { cum += hist[v]; if (cum >= hi_count) { hi = v; break; } }
    if (hi <= lo) { lo = 0; hi = 255; } /* flat image — skip the stretch */

    /* stretched value for each original value */
    int stretched[256];
    for (int v = 0; v < 256; v++) {
        int m = (v - lo) * 255 / (hi - lo);
        stretched[v] = m < 0 ? 0 : (m > 255 ? 255 : m);
    }

    /* histogram in stretched space (many-to-one under clipping is fine) */
    uint64_t shist[256] = {0};
    for (int v = 0; v < 256; v++) shist[stretched[v]] += hist[v];

    /* -- 2. inversion detection on the stretched histogram ---------- */
    double sum = 0.0;
    for (int v = 0; v < 256; v++) sum += (double)v * (double)shist[v];
    int inverted = npixels > 0 && (sum / (double)npixels) < 100.0;
    if (inverted) {
        uint64_t flipped[256];
        for (int v = 0; v < 256; v++) flipped[v] = shist[255 - v];
        for (int v = 0; v < 256; v++) shist[v] = flipped[v];
        sum = 0.0;
        for (int v = 0; v < 256; v++) sum += (double)v * (double)shist[v];
    }

    /* -- 3. Otsu on the final histogram ------------------------------ */
    double sum_b = 0.0, w_b = 0.0, max_var = 0.0;
    int threshold = 127;
    for (int t = 0; t < 256; t++) {
        w_b += (double)shist[t];
        if (w_b == 0.0) continue;
        double w_f = (double)npixels - w_b;
        if (w_f == 0.0) break;
        sum_b += (double)t * (double)shist[t];
        double m_b = sum_b / w_b;
        double m_f = (sum - sum_b) / w_f;
        double between = w_b * w_f * (m_b - m_f) * (m_b - m_f);
        if (between > max_var) { max_var = between; threshold = t; }
    }

    /* -- fold all three steps into one LUT --------------------------- */
    for (int v = 0; v < 256; v++) {
        int s = stretched[v];
        if (inverted) s = 255 - s;
        lut[v] = s > threshold ? 255 : 0;
    }
    return threshold;
}

/* Pass 2: map every pixel through the LUT, in place. */
void apply_lut(uint8_t *gray, size_t npixels, const uint8_t *lut)
{
    for (size_t i = 0; i < npixels; i++) gray[i] = lut[gray[i]];
}

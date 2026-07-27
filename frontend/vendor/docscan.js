/*
 * docscan.js — automatic document-edge detection.
 *
 * Finds the quadrilateral of a document held in front of a camera, so the
 * scanner can auto-crop and de-skew it the way Microsoft Lens does, instead
 * of asking the user to drag four corners by hand.
 *
 * Written in plain JS over typed arrays rather than compiled to WASM. The
 * work happens on a downscaled frame (default 320px wide ≈ 77k pixels), so
 * the whole pipeline costs well under a frame budget — the measured cost is
 * printed by scripts/scanner-test.js. Keeping it as JS preserves the
 * project's no-build-step rule and means the same file works unchanged in
 * the browser, the desktop app and the Android APK.
 *
 * Pipeline:
 *   downscale -> grayscale -> separable Gaussian blur -> Sobel magnitude
 *   -> adaptive threshold -> convex hull of edge points -> best quadrilateral
 *
 * The last step is what makes this robust for documents specifically: a page
 * is convex and roughly rectangular, so rather than tracing contours (which
 * breaks up on shadows and glare) we take the hull of all strong edge pixels
 * and search it for the 4 vertices enclosing the largest area.
 *
 * API:
 *   DocScan.detect(imageData, opts) -> {corners, score, ms} | null
 *   DocScan.orderCorners(pts)       -> [tl, tr, br, bl]
 *   DocScan.warp(srcCanvas, corners, outW, outH) -> canvas
 */
(function (global) {
  'use strict';

  /* ---------- helpers ---------- */

  function toGray(data, w, h) {
    const g = new Uint8ClampedArray(w * h);
    for (let i = 0, p = 0; i < g.length; i++, p += 4) {
      // ITU-R BT.601 luma, integer math — same weights as the C kernel in
      // backend/native/imgproc.c, so on-device and server scans agree.
      g[i] = (data[p] * 306 + data[p + 1] * 601 + data[p + 2] * 117) >> 10;
    }
    return g;
  }

  /* Separable 5-tap Gaussian (sigma ~1). Two 1-D passes instead of a 2-D
     kernel: 10 multiply-adds per pixel rather than 25. */
  function blur(src, w, h) {
    const tmp = new Uint8ClampedArray(w * h);
    const out = new Uint8ClampedArray(w * h);
    const K = [1, 4, 6, 4, 1], NORM = 16;

    for (let y = 0; y < h; y++) {
      const row = y * w;
      for (let x = 0; x < w; x++) {
        let s = 0;
        for (let k = -2; k <= 2; k++) {
          const xx = x + k < 0 ? 0 : (x + k >= w ? w - 1 : x + k);
          s += src[row + xx] * K[k + 2];
        }
        tmp[row + x] = s / NORM;
      }
    }
    for (let x = 0; x < w; x++) {
      for (let y = 0; y < h; y++) {
        let s = 0;
        for (let k = -2; k <= 2; k++) {
          const yy = y + k < 0 ? 0 : (y + k >= h ? h - 1 : y + k);
          s += tmp[yy * w + x] * K[k + 2];
        }
        out[y * w + x] = s / NORM;
      }
    }
    return out;
  }

  /* Sobel gradient magnitude, plus the mean — used to pick a threshold that
     adapts to the scene instead of a fixed constant that fails in low light. */
  function sobel(src, w, h) {
    const mag = new Uint16Array(w * h);
    let sum = 0;
    for (let y = 1; y < h - 1; y++) {
      for (let x = 1; x < w - 1; x++) {
        const i = y * w + x;
        const tl = src[i - w - 1], t = src[i - w], tr = src[i - w + 1];
        const l = src[i - 1], r = src[i + 1];
        const bl = src[i + w - 1], b = src[i + w], br = src[i + w + 1];
        const gx = (tr + 2 * r + br) - (tl + 2 * l + bl);
        const gy = (bl + 2 * b + br) - (tl + 2 * t + tr);
        const m = Math.abs(gx) + Math.abs(gy);   // L1: no sqrt, same ordering
        mag[i] = m;
        sum += m;
      }
    }
    return { mag, mean: sum / (w * h) };
  }

  function cross(o, a, b) {
    return (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x);
  }

  /* Andrew's monotone chain convex hull. O(n log n), and the sort dominates. */
  function convexHull(pts) {
    if (pts.length < 3) return pts.slice();
    const p = pts.slice().sort((a, b) => (a.x - b.x) || (a.y - b.y));
    const lower = [];
    for (const pt of p) {
      while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], pt) <= 0) lower.pop();
      lower.push(pt);
    }
    const upper = [];
    for (let i = p.length - 1; i >= 0; i--) {
      const pt = p[i];
      while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], pt) <= 0) upper.pop();
      upper.push(pt);
    }
    lower.pop(); upper.pop();
    return lower.concat(upper);
  }

  function polyArea(q) {
    let a = 0;
    for (let i = 0, n = q.length; i < n; i++) {
      const p1 = q[i], p2 = q[(i + 1) % n];
      a += p1.x * p2.y - p2.x * p1.y;
    }
    return Math.abs(a) / 2;
  }

  /* The 4 hull vertices enclosing the largest area.
   *
   * A document is convex, so its corners are hull vertices — but the hull may
   * have dozens of points from noise along the edges. Rather than an O(n^4)
   * search, walk the hull keeping the 4 points that maximise area, seeded by
   * the extremes along both diagonals. This is the standard approximation and
   * it is exact for a clean rectangle. */
  function largestQuad(hull) {
    const n = hull.length;
    if (n < 4) return null;
    if (n === 4) return hull.slice();

    // Seed from extremes: these are corners for any near-rectangular shape.
    let minSum = 0, maxSum = 0, minDiff = 0, maxDiff = 0;
    for (let i = 1; i < n; i++) {
      const s = hull[i].x + hull[i].y, d = hull[i].x - hull[i].y;
      if (s < hull[minSum].x + hull[minSum].y) minSum = i;
      if (s > hull[maxSum].x + hull[maxSum].y) maxSum = i;
      if (d < hull[minDiff].x - hull[minDiff].y) minDiff = i;
      if (d > hull[maxDiff].x - hull[maxDiff].y) maxDiff = i;
    }
    let best = [hull[minSum], hull[maxDiff], hull[maxSum], hull[minDiff]];
    let bestArea = polyArea(best);

    // Refine: try replacing each vertex with every other hull point.
    for (let pass = 0; pass < 2; pass++) {
      for (let v = 0; v < 4; v++) {
        for (let i = 0; i < n; i++) {
          const cand = best.slice();
          cand[v] = hull[i];
          // Reject degenerate quads where two vertices collapsed together.
          let ok = true;
          for (let a = 0; a < 4 && ok; a++) {
            for (let b = a + 1; b < 4; b++) {
              if (cand[a].x === cand[b].x && cand[a].y === cand[b].y) { ok = false; break; }
            }
          }
          if (!ok) continue;
          const area = polyArea(cand);
          if (area > bestArea) { bestArea = area; best = cand; }
        }
      }
    }
    return best;
  }

  /* ---------- public API ---------- */

  /**
   * Detect the document quad in an ImageData.
   * @returns {{corners: Array<{x,y}>, score: number, ms: number}|null}
   *   corners are in the ImageData's own coordinate space, clockwise from
   *   top-left. `score` is the fraction of the frame the quad covers.
   */
  function detect(imageData, opts) {
    const t0 = (global.performance || Date).now();
    opts = opts || {};
    const work = opts.workWidth || 320;
    // Minimum fraction of the frame the quad must cover. Low enough to catch
    // a receipt held well back from the camera (measured at ~11% of frame),
    // high enough that noise and small background objects are ignored — the
    // blank-frame case in scripts/scanner-test.js guards the lower bound.
    const minCover = opts.minCoverage != null ? opts.minCoverage : 0.07;

    const sw = imageData.width, sh = imageData.height;
    // Downscale by an integer step: cheap, and plenty for edge finding.
    const step = Math.max(1, Math.round(sw / work));
    const w = Math.floor(sw / step), h = Math.floor(sh / step);
    if (w < 16 || h < 16) return null;

    // Subsample straight into a small RGBA buffer.
    const small = new Uint8ClampedArray(w * h * 4);
    const src = imageData.data;
    for (let y = 0; y < h; y++) {
      const sy = y * step;
      for (let x = 0; x < w; x++) {
        const si = (sy * sw + x * step) * 4, di = (y * w + x) * 4;
        small[di] = src[si]; small[di + 1] = src[si + 1];
        small[di + 2] = src[si + 2]; small[di + 3] = 255;
      }
    }

    const gray = toGray(small, w, h);
    const blurred = blur(gray, w, h);
    const { mag, mean } = sobel(blurred, w, h);

    // Adaptive: keep edges well above the scene's average gradient. The
    // floor stops a blank frame producing noise-only "edges".
    const thresh = Math.max(24, mean * 2.2);

    const pts = [];
    // Ignore a 2px border: the frame edge is itself a strong gradient and
    // would otherwise be detected as the document every time.
    for (let y = 2; y < h - 2; y++) {
      for (let x = 2; x < w - 2; x++) {
        if (mag[y * w + x] > thresh) pts.push({ x, y });
      }
    }
    if (pts.length < 16) return null;

    const hull = convexHull(pts);
    const quad = largestQuad(hull);
    if (!quad) return null;

    const score = polyArea(quad) / (w * h);
    if (score < minCover) return null;

    // Back to the caller's coordinate space.
    const corners = orderCorners(quad).map(p => ({ x: p.x * step, y: p.y * step }));
    return { corners, score, ms: (global.performance || Date).now() - t0 };
  }

  /** Order 4 points clockwise from top-left. */
  function orderCorners(pts) {
    const cx = pts.reduce((s, p) => s + p.x, 0) / pts.length;
    const cy = pts.reduce((s, p) => s + p.y, 0) / pts.length;
    return pts.slice().sort((a, b) =>
      Math.atan2(a.y - cy, a.x - cx) - Math.atan2(b.y - cy, b.x - cx))
      .reduce((acc, p) => acc.concat([p]), [])
      // rotate so the top-left (smallest x+y) comes first
      .reduce((acc, _, i, arr) => {
        if (i > 0) return acc;
        let start = 0, best = Infinity;
        arr.forEach((p, j) => { const s = p.x + p.y; if (s < best) { best = s; start = j; } });
        return arr.slice(start).concat(arr.slice(0, start));
      }, []);
  }

  /**
   * Perspective-correct the quad into a flat rectangle.
   * Inverse-maps each destination pixel through the homography, so there are
   * no gaps — forward mapping leaves holes wherever the source is stretched.
   */
  function warp(srcCanvas, corners, outW, outH) {
    const [tl, tr, br, bl] = corners;
    const sctx = srcCanvas.getContext('2d', { willReadFrequently: true });
    const sd = sctx.getImageData(0, 0, srcCanvas.width, srcCanvas.height);
    const sw = sd.width, sh = sd.height, s = sd.data;

    const out = document.createElement('canvas');
    out.width = outW; out.height = outH;
    const octx = out.getContext('2d');
    const od = octx.createImageData(outW, outH);
    const d = od.data;

    for (let y = 0; y < outH; y++) {
      const v = y / (outH - 1);
      // Bilinear interpolation across the quad's edges is exact for the
      // affine case and a good approximation of the projective one at the
      // angles a handheld scan actually produces.
      const ax = tl.x + (bl.x - tl.x) * v, ay = tl.y + (bl.y - tl.y) * v;
      const bx = tr.x + (br.x - tr.x) * v, by = tr.y + (br.y - tr.y) * v;
      for (let x = 0; x < outW; x++) {
        const u = x / (outW - 1);
        const fx = ax + (bx - ax) * u, fy = ay + (by - ay) * u;
        const sx = fx < 0 ? 0 : (fx > sw - 1 ? sw - 1 : fx);
        const sy = fy < 0 ? 0 : (fy > sh - 1 ? sh - 1 : fy);
        const x0 = sx | 0, y0 = sy | 0;
        const x1 = x0 + 1 < sw ? x0 + 1 : x0, y1 = y0 + 1 < sh ? y0 + 1 : y0;
        const dx = sx - x0, dy = sy - y0;
        const i00 = (y0 * sw + x0) * 4, i10 = (y0 * sw + x1) * 4;
        const i01 = (y1 * sw + x0) * 4, i11 = (y1 * sw + x1) * 4;
        const di = (y * outW + x) * 4;
        for (let c = 0; c < 3; c++) {
          const top = s[i00 + c] + (s[i10 + c] - s[i00 + c]) * dx;
          const bot = s[i01 + c] + (s[i11 + c] - s[i01 + c]) * dx;
          d[di + c] = top + (bot - top) * dy;
        }
        d[di + 3] = 255;
      }
    }
    octx.putImageData(od, 0, 0);
    return out;
  }

  /** Are two detections close enough to call the frame steady? */
  function isStable(a, b, tolerance) {
    if (!a || !b) return false;
    const tol = tolerance || 12;
    for (let i = 0; i < 4; i++) {
      if (Math.abs(a[i].x - b[i].x) > tol || Math.abs(a[i].y - b[i].y) > tol) return false;
    }
    return true;
  }

  global.DocScan = { detect, orderCorners, warp, isStable };
})(typeof window !== 'undefined' ? window : globalThis);

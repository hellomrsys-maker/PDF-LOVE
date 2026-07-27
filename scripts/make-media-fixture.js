/*
 * Generate the video and audio fixtures using a real browser.
 *
 *   node scripts/make-media-fixture.js <out-dir>
 *
 * Why not ffmpeg: the only ffmpeg reliably available alongside Playwright is
 * its bundled screen-capture build, which has no lavfi, no rawvideo, no
 * image2 and no pipe protocol — it cannot synthesise media at all. Rather
 * than make the fixtures depend on a system package that may not be there,
 * this records a canvas with MediaRecorder.
 *
 * That is also the more honest fixture: it is produced by exactly the API
 * the app's own Screen Recorder uses, and decoded by exactly the engine the
 * video tools use. A file ffmpeg produced might be encoded in a way the
 * browser handles differently.
 */
const path = require('path');
const fs = require('fs');
const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright');

const out = process.argv[2] || path.join(__dirname, '..', 'fixtures');

(async () => {
  const browser = await chromium.launch({
    args: ['--autoplay-policy=no-user-gesture-required'],
  });
  const page = await browser.newPage();
  await page.goto('about:blank');

  const media = await page.evaluate(async () => {
    /** Record an animated canvas, with a tone mixed in, to WebM. */
    async function record(seconds, withAudio) {
      const c = document.createElement('canvas');
      c.width = 480; c.height = 360;
      const g = c.getContext('2d');

      let frame = 0;
      const draw = () => {
        g.fillStyle = '#f5f3ec'; g.fillRect(0, 0, 480, 360);
        g.fillStyle = '#c1683a';
        g.beginPath();
        g.arc(80 + (frame * 6) % 320, 130, 60, 0, Math.PI * 2);
        g.fill();
        g.fillStyle = '#4a7856';
        g.fillRect(20, 300, (frame * 8) % 440, 40);
        g.fillStyle = '#1f2420';
        g.font = '20px sans-serif';
        g.fillText('frame ' + (++frame), 20, 40);
      };
      const timer = setInterval(draw, 1000 / 15);
      draw();

      const stream = c.captureStream(15);

      if (withAudio) {
        // A real audio track, so "extract audio" has something to extract.
        const ac = new AudioContext();
        const osc = ac.createOscillator();
        const dest = ac.createMediaStreamDestination();
        osc.type = 'sine';
        osc.frequency.value = 440;
        osc.connect(dest);
        osc.start();
        dest.stream.getAudioTracks().forEach(t => stream.addTrack(t));
      }

      const chunks = [];
      const rec = new MediaRecorder(stream, { mimeType: 'video/webm' });
      rec.ondataavailable = e => { if (e.data.size) chunks.push(e.data); };
      rec.start();
      await new Promise(r => setTimeout(r, seconds * 1000));
      await new Promise(r => { rec.onstop = r; rec.stop(); });
      clearInterval(timer);

      const blob = new Blob(chunks, { type: 'video/webm' });
      const buf = await blob.arrayBuffer();
      return Array.from(new Uint8Array(buf));
    }

    /** A standalone WAV, written by hand — no encoder needed. */
    function wav(seconds, freq) {
      const rate = 44100, n = rate * seconds;
      const buf = new ArrayBuffer(44 + n * 2);
      const v = new DataView(buf);
      const str = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
      str(0, 'RIFF'); v.setUint32(4, 36 + n * 2, true); str(8, 'WAVE');
      str(12, 'fmt '); v.setUint32(16, 16, true);
      v.setUint16(20, 1, true); v.setUint16(22, 1, true);
      v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true);
      v.setUint16(32, 2, true); v.setUint16(34, 16, true);
      str(36, 'data'); v.setUint32(40, n * 2, true);
      for (let i = 0; i < n; i++) {
        v.setInt16(44 + i * 2, Math.sin(2 * Math.PI * freq * i / rate) * 20000, true);
      }
      return Array.from(new Uint8Array(buf));
    }

    return {
      video: await record(4, true),
      videoNoAudio: await record(2, false),
      audio: wav(3, 440),
    };
  });

  fs.writeFileSync(path.join(out, 'clip.webm'), Buffer.from(media.video));
  fs.writeFileSync(path.join(out, 'clip-silent.webm'), Buffer.from(media.videoNoAudio));
  fs.writeFileSync(path.join(out, 'audio.wav'), Buffer.from(media.audio));

  for (const f of ['clip.webm', 'clip-silent.webm', 'audio.wav']) {
    const p = path.join(out, f);
    const size = fs.statSync(p).size;
    if (size < 1024) {
      console.error(`FAIL: ${f} is only ${size} bytes — recording produced nothing`);
      process.exit(1);
    }
    console.log(`  ${f.padEnd(18)} ${(size / 1024).toFixed(0)} KB`);
  }

  await browser.close();
})();

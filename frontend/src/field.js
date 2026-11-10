/**
 * ASCII-поле фона — дословный перенос из sdk-hub/demo (index.html, createTexture).
 *
 * Отличия от оригинала ровно два и оба снаружи поля:
 *   1) не подключаются обработчики pointermove/pointerdown — поэтому массивы
 *      taps/trail и скаляр heat остаются пустыми, и draw() рисует чистое поле
 *      без всплесков, следов и «тепловых» пятен;
 *   2) режим движения по умолчанию 'auto' (без localStorage-настройки).
 * Всё, что относится к самому полю — сетка, три слоя domain-warping,
 * пороги sea/tex/gust, атлас глифов и батчинг — оставлено без изменений.
 */

  const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
  const smoothstep = (a, b, x) => {
    let t = (x - a) / (b - a);
    t = t < 0 ? 0 : t > 1 ? 1 : t;
    return t * t * (3 - 2 * t);
  };
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* file:// бывает запрещён */ } }
  };

  // таблица синуса вместо Math.sin в горячем цикле
  const SIN_N = 2048, SIN_MASK = SIN_N - 1, SIN_K = SIN_N / (Math.PI * 2);
  const SIN = new Float32Array(SIN_N);
  for (let i = 0; i < SIN_N; i++) SIN[i] = Math.sin((i * Math.PI * 2) / SIN_N);
  const sinT = (a) => SIN[((a * SIN_K) | 0) & SIN_MASK];

  // сглаженный value-noise: даёт волокна, а не «пыль»
  const NL = 1024;
  const NLAT = new Float32Array(NL);
  for (let i = 0; i < NL; i++) NLAT[i] = Math.random();
  const lat = (x, y) => NLAT[(Math.imul(x, 0x27d4eb2d) ^ Math.imul(y, 0x165667b1)) & (NL - 1)];
  function noise2(x, y) {
    const xi = Math.floor(x), yi = Math.floor(y);
    const xf = x - xi, yf = y - yi;
    const sx = xf * xf * (3 - 2 * xf);
    const sy = yf * yf * (3 - 2 * yf);
    const a = lat(xi, yi), b = lat(xi + 1, yi);
    const c = lat(xi, yi + 1), e = lat(xi + 1, yi + 1);
    const top = a + (b - a) * sx;
    const bot = c + (e - c) * sx;
    return top + (bot - top) * sy;
  }

  const RAMP = " !\"#$%&'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\\]^_`abcdefghijklmnopqrstuvwxyz{|}~·";
  const LOOKS = {
    mixed: 'ab0cAde1fEgh2iGjk3lHmn4oKpq5rMst6uRvw7xSyz8nT9eW',
    lettered: 'abcd3efgRhijk7lmnAopqr0stuEvwxy5zaeKiou2gcS9',
    figured: '0a1b2C3d4e5F6g7h8i9J0k1m2N3p4q5R6s7t8U9v0w1X2y3z'
  };
  const LEVELS = 24;
  const COLORS = 13;         // 0 — фон, 1..12 — непрерывный синий → тёплый
  const MONO = 'ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace';


  export function createField(container, opts = {}) {
    const canvas = document.createElement('canvas');
    canvas.style.cssText = 'position:absolute;inset:0;width:100%;height:100%;display:block';
    container.appendChild(canvas);
    const ctx = canvas.getContext('2d', { alpha: true });
    if (!ctx) return null;

    const reducedQuery = matchMedia('(prefers-reduced-motion: reduce)');
    const DEBUG = location.search.includes('debug');
    const INSTANT = location.search.includes('instant');

    const P = {
      targetCells: opts.cells || 15000,
      // cellMin/cellMax — ячейка мельче референса: поле плотнее и читается
      // волной, а не набором букв. glyphRatio на 13% меньше оригинала —
      // это и есть просьба «буквы чуть уменьшить», но глиф ещё узнаваем.
      cellMin: 4.0,
      cellMax: 14,
      weight: 300,
      glyphRatio: 1.2,
      // 10 fps вместо 16 мс у референса. Поле меняется медленно: за 100 мс
      // волна сдвигается на единицы пикселей. Ограничение нужно не ради
      // экономии, а ради стабильности: на 60 fps рендерер падал через 7-9 с
      // (ровно так же со штатным демо-референсом), на 30 — через 12 с,
      // на 20 — через 11 с, на 10 — держится. Оно снимает именно тот объём
      // растеризации, на котором рендерер срывался.
      frameMs: 100,
      speed: 52,
      heading: 0.34
    };

    const atlas = document.createElement('canvas');
    const actx = atlas.getContext('2d');

    let cols = 0, rows = 0, cellW = 0, cellH = 0, dpr = 1;
    let cssW = 0, cssH = 0;
    let glyphLook = [];
    let lookPick = null;
    let glyphPace = null;     // у каждой ячейки своя стартовая точка в наборе
    let glyphSpeed = null;    // и своя скорость перебора
    let calmArr = null;
    let cx = null, cy = null, uu = null, vv = null;

    const bucketCount = COLORS * LEVELS;
    let bufX = [], bufY = [], bufG = [];
    let bufCap = 0;
    const bufLen = new Int32Array(bucketCount);

    const taps = [];
    const trail = [];

    // искажение пространства: точка выборки смещается шумом,
    // поэтому волна идёт не идеальным кольцом, а живой неровной формой
    let warpX = null, warpY = null;
    let warpAt = -1e9;

    function refreshWarp(nowMs) {
      if (!cx || (nowMs - warpAt) < 90) return;
      warpAt = nowMs;
      const n = cols * rows;
      if (!warpX || warpX.length !== n) {
        warpX = new Float32Array(n);
        warpY = new Float32Array(n);
      }
      const tt = time * 0.12;
      for (let k = 0; k < n; k++) {
        const x = cx[k], y = cy[k];
        warpX[k] = 11.5 * noise2(x / 95 + tt, y / 95 + 0.5);
        warpY[k] = 11.5 * noise2(x / 95 + 9.1 - tt, y / 95 + 4.5);
      }
    }

    let time = 0, lastInteract = performance.now();
    let energy = 0;

    // ── нагрев ровно как в оригинале ──
    // n  — накопленный импульс кликов (кап 1.5, распад τ = 2.2 с)
    // heatTarget — smoothstep((n - 0.4) / 0.9): пока n <= 0.4 это НОЛЬ,
    // поэтому первые два клика ничего не красят, а дальше цвет плавно теплеет.
    let heatImpulse = 0;      // n
    let heat = 0;             // r — сглаженный жар, идёт в отрисовку

    // пятно нагрева: x, y — сглаженная позиция курсора, r — радиус,
    // s — сила. Ровно как uniform vec4 u_heat в шейдере.
    const spot = { x: innerWidth / 2, y: innerHeight / 2, r: 1, s: 0 };
    let raf = 0, lastDraw = 0, running = true, destroyed = false;

    /* ── режим движения ───────────────────────────────────
       auto — уважаем системную настройку, но НЕ замораживаем:
              при reduce поле живёт, просто тише и спокойнее
       full — полная амплитуда всегда
       calm — принудительно спокойный режим                 */
    let motion = 'auto';
    const urlMotion = (location.search.match(/motion=(auto|full|calm)/) || [])[1];
    if (urlMotion) motion = urlMotion;

    function motionProfile() {
      if (motion === 'calm') return { slow: 0.55, scale: 0.6 };
      if (motion === 'full') return { slow: 1, scale: 1 };
      return reducedQuery.matches
        ? { slow: 0.62, scale: 0.8 }   // не ноль: анимация остаётся живой
        : { slow: 1, scale: 1 };
    }

    function pickLook() {
      const keys = Object.keys(LOOKS);
      let recent = [];
      try { recent = JSON.parse(store.get('demo:looks') || '[]'); } catch (e) { recent = []; }
      if (!Array.isArray(recent)) recent = [];
      const fresh = keys.filter((k) => !recent.includes(k));
      const pool = fresh.length ? fresh : keys.filter((k) => k !== recent[0]);
      const key = pool[Math.floor(Math.random() * pool.length)] || 'mixed';
      store.set('demo:looks', JSON.stringify([key, ...recent.filter((k) => k !== key)].slice(0, 3)));
      return LOOKS[key];
    }

    function buildLookMap() {
      const chars = [...pickLook()];
      glyphLook = chars.map((ch) => {
        const i = RAMP.indexOf(ch);
        return i < 0 ? RAMP.indexOf('.') : i;
      }).filter((i) => i > 0);
      if (!glyphLook.length) glyphLook = [RAMP.indexOf('.')];
    }

    /* Палитра строится интерполяцией, как в оригинале:
       mix(u_glowColor, HEAT_GLOW, t), где HEAT_GLOW = 0.86, 0.42, 0.30.
       Это тёплый красно-оранжевый, а не чистый красный. */
    function palette() {
      // opts.dark задаёт хост: у CYBRA тёмная тема без data-theme на <html>
      const dark = opts.dark !== undefined
        ? !!opts.dark
        : document.documentElement.dataset.theme === 'dark';
      const css = (getComputedStyle(container).color || '').trim() || (dark ? '#a8a69e' : '#74726c');

      // холодный «пузырь» и тёплый «нагрев»
      const cool = dark ? [0.30, 0.76, 1.00] : [0.14, 0.28, 0.91];
      const warm = [0.86, 0.42, 0.30];

      const out = [css];
      const steps = COLORS - 1;
      for (let i = 1; i <= steps; i++) {
        const t = i / steps;
        const r = Math.round((cool[0] + (warm[0] - cool[0]) * t) * 255);
        const g = Math.round((cool[1] + (warm[1] - cool[1]) * t) * 255);
        const b = Math.round((cool[2] + (warm[2] - cool[2]) * t) * 255);
        out.push('rgb(' + r + ',' + g + ',' + b + ')');
      }
      return out;
    }

    /* ── атлас: COLORS палитр × LEVELS прозрачностей ── */
    function buildAtlas() {
      const colors = palette();
      atlas.width = Math.max(1, RAMP.length * cellW);
      atlas.height = Math.max(1, COLORS * LEVELS * cellH);
      actx.setTransform(1, 0, 0, 1, 0, 0);
      actx.clearRect(0, 0, atlas.width, atlas.height);
      actx.textAlign = 'center';
      actx.textBaseline = 'middle';
      actx.font = `${P.weight} ${Math.round(cellW * P.glyphRatio)}px ${MONO}`;

      for (let c = 0; c < COLORS; c++) {
        actx.fillStyle = colors[c];
        for (let l = 0; l < LEVELS; l++) {
          // l = 0 → alpha 0 (невидимо), l = LEVELS-1 → почти непрозрачно
          actx.globalAlpha = l / (LEVELS - 1);
          const y0 = (c * LEVELS + l) * cellH + cellH / 2;
          for (let g = 0; g < RAMP.length; g++) {
            actx.fillText(RAMP[g], g * cellW + cellW / 2, y0);
          }
        }
      }
      actx.globalAlpha = 1;
    }

    function layout() {
      const w = container.clientWidth || innerWidth;
      const h = container.clientHeight || innerHeight;
      if (!w || !h) return false;
      dpr = Math.min(window.devicePixelRatio || 1, 2);

      let cellCss = Math.sqrt((w * h) / (2 * P.targetCells));
      cellCss = clamp(cellCss, P.cellMin, P.cellMax);
      cellW = Math.max(5, Math.round(cellCss * dpr));
      cellH = cellW * 2;
      cols = Math.max(1, Math.ceil((w * dpr) / cellW));
      rows = Math.max(1, Math.ceil((h * dpr) / cellH));

      let guard = 0;
      while (cols * rows * cellW * cellH > 21e6 && guard++ < 8) {
        cellW += 1;
        cellH = cellW * 2;
        cols = Math.max(1, Math.ceil((w * dpr) / cellW));
        rows = Math.max(1, Math.ceil((h * dpr) / cellH));
      }

      canvas.width = cols * cellW;
      canvas.height = rows * cellH;
      cssW = (cols * cellW) / dpr;
      cssH = (rows * cellH) / dpr;

      const n = cols * rows;
      if (!glyphLook.length) buildLookMap();
      cx = new Float32Array(n);
      cy = new Float32Array(n);
      uu = new Float32Array(n);
      vv = new Float32Array(n);
      lookPick = new Uint8Array(n);
      glyphPace = new Uint8Array(n);
      glyphSpeed = new Float32Array(n);
      calmArr = new Float32Array(n);

      const c = Math.cos(P.heading), s = Math.sin(P.heading);
      const cw = cellW / dpr, chh = cellH / dpr;
      const calX = cssW * 0.5, calY = cssH * 0.4;
      const rx = cssW * 0.32, ry = cssH * 0.32;

      for (let j = 0; j < rows; j++) {
        for (let i = 0; i < cols; i++) {
          const k = j * cols + i;
          const x = (i + 0.5) * cw;
          const y = (j + 0.5) * chh;
          cx[k] = x;
          cy[k] = y;
          uu[k] = x * c + y * s;
          vv[k] = -x * s + y * c;
          lookPick[k] = (Math.random() * glyphLook.length) | 0;
          glyphPace[k] = (Math.random() * 256) | 0;
          // 0.6 .. 1.4 — как (0.6 + 0.8 * unit(pace)) в шейдере
          glyphSpeed[k] = 0.6 + 0.8 * Math.random();
          const ox = (x - calX) / rx;
          const oy = (y - calY) / ry;
          calmArr[k] = 1 - 0.93 * Math.exp(-1.1 * (ox * ox + oy * oy));
        }
      }

      // Буферы заводятся лениво и растут по мере надобности. Референс держал
      // массив на n ячеек для всех 312 бакетов сразу — на 1440x900 это ~44 МБ
      // пустых Int32Array плюс атлас, и вкладка падала по памяти.
      if (!bufX.length || n > bufCap) {
        bufCap = n;
        bufX = []; bufY = []; bufG = [];
        for (let b = 0; b < bucketCount; b++) {
          bufX[b] = new Int32Array(0);
          bufY[b] = new Int32Array(0);
          bufG[b] = new Uint8Array(0);
        }
      }
      for (let b = 0; b < bucketCount; b++) { bufLen[b] = 0; }

      buildAtlas();
      return true;
    }

    function step(dt) {
      const prof = motionProfile();
      const idle = (performance.now() - lastInteract) / 1000;
      const calm = idle > 15 ? 0.72 : 1;
      time += Math.min(dt, 0.1) * prof.slow * (1 + energy * 0.7) * calm;
      // ── нагрев по формулам оригинала ──
      const dts = Math.min(dt, 0.1);
      heatImpulse *= Math.exp(-dts / 2.2);
      const want = smoothstep(0.4, 1.3, heatImpulse);   // = smoothstep((n-.4)/.9)
      heat += (want - heat) * Math.min(1, dts * 4);     // r плавно идёт к цели
      if (heat < 0.0008) heat = 0;

      spot.r = Math.max(cssW, cssH) * 0.28;
      spot.s = heat;

      energy *= Math.exp(-dt / 2.2);
      if (energy < 0.002) energy = 0;
    }

    function draw() {
      const w = canvas.width, h = canvas.height;
      ctx.clearRect(0, 0, w, h);

      const prof = motionProfile();
      const t = time;
      const flow = t * 46;
      const gustPhase = t * 0.18;
      const amp = prof.scale;

      const live = [];
      const now = performance.now();
      const LIFE = 4.0;                 // полная жизнь волны
      const REACH = 300;                // радиус вдвое меньше прежнего
      for (let i = taps.length - 1; i >= 0; i--) {
        const tp = taps[i];
        const age = (now - tp.t0) / 1000;
        if (age > LIFE) { taps.splice(i, 1); continue; }

        const reach = REACH * (1 - Math.exp(-age / 0.95));
        const width = 41 + 29 * age;

        // Спад без ступеньки: экспонента держит форму, а (1-age/LIFE)^2.5
        // гарантированно приводит к нулю ровно к концу жизни.
        // Плюс отдельный «хвост» — последние 60% времени гаснут медленно.
        const lin = Math.max(0, 1 - age / LIFE);
        const tail = Math.exp(-age / 3.4);
        const fade = Math.pow(lin, 2.5) * (0.35 + 0.65 * tail);
        const decay = Math.exp(-age / 2.4);

        live.push({
          x: tp.x, y: tp.y,
          reach,
          w: width,
          age,
          amp: tp.s * Math.exp(-age / 1.25) * fade * amp,
          s: tp.s
        });
      }
      const tapN = live.length;
      const trailN = trail.length;
      if (tapN) refreshWarp(now);

      bufLen.fill(0);
      let total = 0;

      for (let j = 0; j < rows; j++) {
        const rowBase = j * cols;
        for (let i = 0; i < cols; i++) {
          const k = rowBase + i;

          // ── ветер: «море» из завихрений, как gustsAt в оригинале ──
          // Три слоя: крупные вихри → средние складки → мелкая рябь.
          // Каждый слой сдвигает координаты следующего (domain warping),
          // поэтому вместо полосок получаются живые закрученные струи.
          const uPx = uu[k] - flow;
          const vPx = vv[k];

          // слой 1: крупные водовороты, масштаб ~110 px
          const e1x = uPx / 110 + t * 0.035;
          const e1y = vPx / 110 - t * 0.02;
          const eddyX = noise2(e1x, e1y);
          const eddyY = noise2(e1x + 31.7, e1y + 3.0);

          // слой 2: складки, ведомые вихрем, масштаб ~38 px
          const f2x = (uPx + 42 * eddyX) / 38 + t * 0.05;
          const f2y = (vPx + 42 * eddyY) / 38 + t * 0.03;
          const foldX = noise2(f2x, f2y);
          const foldY = noise2(f2x + 13.1, f2y + 7.0);

          // слой 3: совсем мелкая рябь, пара строк символов
          const t3x = (uPx + 26 * foldX) / 15 + t * 0.07;
          const t3y = (vPx + 26 * foldY) / 15 + t * 0.05;
          const tiny = noise2(t3x, t3y);

          // ── где вообще есть море ──
          // Две шкалы: крупные «заливы» и средние «отмели». Их пересечение
          // даёт настоящие дыры — районы, где букв нет совсем.
          // В шейдере это порог blowing: ниже него не рисуется ничего.
          const bayA = noise2(uPx / 260 - t * 0.010, vPx / 260 + 0.5);
          const bayB = noise2(uPx / 90 + t * 0.016 + 7.3, vPx / 90 - 4.1);
          const sea = bayA * 0.62 + bayB * 0.38;

          // наличие моря: 0 — чистая зона, 1 — вода
          const presence = smoothstep(0.42, 0.56, sea);

          // ── фактура внутри моря: вихри + складки + рябь ──
          const detail = eddyX * 0.46 + foldX * 0.34 + tiny * 0.20;

          // порывы вдоль ветра
          const gust = 0.62 + 0.38 * sinT(uPx * 0.0016 + vPx * 0.0038 - gustPhase);

          // плотность: «есть ли море» × фактура
          // фактура тоже пороговая: внутри залива есть и свои пустоты,
          // иначе получается ровная «стена» из букв
          const tex = smoothstep(0.30, 0.62, detail);
          let d = presence * tex * gust;
          d *= calmArr[k];
          const x = cx[k], y = cy[k];

          let warmth = 0;              // мягкое свечение под курсором

          // ── след курсора ──
          if (trailN) {
            // warmthAt(): каждая точка пути остывает по exp(-age / de),
            // de = 0.65 c — поэтому свет под курсором тает, а не гаснет
            let warm = 0;
            for (let p = 0; p < trailN; p++) {
              const tp = trail[p];
              const ageS = (now - tp.t) / 1000;
              const decayW = Math.exp(-ageS / 0.45) * (1 - Math.exp(-ageS / 0.04));
              if (decayW < 0.004) continue;
              const dx = x - tp.x, dy = y - tp.y;
              const r = 60 + 40 * ageS;
              const r2 = dx * dx + dy * dy;
              if (r2 < r * r) warm += tp.heat * decayW * (1 - r2 / (r * r));
            }
            // след — самостоятельный слой: он не должен зависеть
            // от того, есть ли в этом месте рисунок моря
            if (warm > 0) warmth = (1 - Math.exp(-1.5 * warm)) * 0.6;
          }

          // ── волны от кликов: четыре независимых слоя, как в tapsAt() ──
          let vx = 0, vy = 0, push = 0;      // толчок воздуха (xy) + его сила
          let raise = 0;                     // знаковый подъём (для яркости)
          let bandMax = 0;                   // яркость гребня 0..1
          let ringMax = 0;                   // свет от дискретных фронтов
          let zone = 0;                      // где волна вообще есть
          let waveMask = 0;                  // насколько тут вообще волна
          let excite = 0;                    // возбуждение → перебор глифов
          let glowA = 0;                     // вспышка: короткая, τ=1.0
          let glowB = 0;                     // послесветие: длинное, τ=1.2
          let colorHeat = 0;                 // жар в этой точке

          for (let q = 0; q < tapN; q++) {
            const tp = live[q];
            // рваный контур: точка выборки смещается шумом
            const wx = x + warpX[k];
            const wy = y + warpY[k];
            const dx = wx - tp.x, dy = wy - tp.y;
            const d = Math.sqrt(dx * dx + dy * dy) || 0.001;
            if (d > tp.reach + tp.w * 4) continue;

            // behind > 0 внутри фронта, < 0 снаружи
            const behind = tp.reach - d;
            const qb = behind / tp.w;
            // бугор: резко встаёт на фронте и плавно сходит вглубь —
            // ровно exp(-behind² / width²) из шейдера
            const front = smoothstep(-16, 10, behind) * Math.exp(-qb * qb);
            const swell = tp.amp * front;
            if (swell < 0.0008) continue;

            // толчок наружу — ровный, без качания
            const inv = swell * 44 / d;
            vx += dx * inv;
            vy += dy * inv;
            push += swell;

            // СЛОЙ 2 — гребни. Ровно формула шейдера:
            //   z += 1.9 * swell * (0.25 + 0.75 * cos(behind * 2π/период))
            // Окно одно — гауссов бугор в swell. Период подобран под наш
            // радиус (вдвое меньше оригинала), поэтому в окне укладывается
            // 2–3 гребня и они идут отдельными волнами, а не одной полосой.
            // Лёгкий шумовой сдвиг фазы не даёт кольцам быть идеальными.
            // У гребней СВОЁ окно, шире чем у толчка: иначе гауссов
            // бугор гасит косинус раньше, чем тот даст вторую волну.
            // ── волна: непрерывная, без скачков ──
          // Одна формула на всё: кольца = cos(behind/период), запертый
          // в гауссовом окне. Никаких пороговых переключений —
          // именно они давали «телепорт» и заливку диска.
          // Период 88 px: при радиусе до 300 в окно влезает 2–3 кольца,
          // а не 4 — как у оригинала.
          const RING_PERIOD = 88;
          const wobble = noise2(wx * 0.02 + tp.age * 0.35, wy * 0.02) * 0.5;
          const ring = Math.cos(behind * (6.2831853 / RING_PERIOD) + wobble);

          // окно волны: расширяется с возрастом, как width в шейдере.
          const windowW = smoothstep(-18, 14, behind) * Math.exp(-qb * qb * 0.55);

          // Спад по номеру кольца: 1-е (у фронта) самое яркое,
          // 2-е примерно вдвое слабее, 3-е — ещё слабее.
          const ringIdx = Math.max(0, behind) / RING_PERIOD;
          const ringDecay = Math.exp(-ringIdx * 0.80);

          // яркость гребня 0..1 — сглаженная, а не thresholded
          const ridge = windowW * (0.30 + 0.70 * ring) * ringDecay;
          if (ridge > ringMax) ringMax = ridge;

          // толчок воздуха (только наружу, ровный)
          const pushRing = tp.amp * ridge;
          if (pushRing > 0.003) {
            const inv = pushRing * 30 / d;
            vx += dx * inv;
            vy += dy * inv;
          }

          // «покров» — насколько волна вообще присутствует в точке.
          // Считается ТЕМ ЖЕ окном, поэтому нет шва между зоной и фоном.
          const coverHere = windowW * Math.min(1, tp.amp * 1.8);
          if (coverHere > zone) zone = coverHere;

          excite += ridge;

          // СЛОЙ 3/4 — вспышка у фронта и послесветие позади
          const trail = smoothstep(0, 70, behind) * Math.exp(-Math.max(behind, 0) / 260);
          glowA += Math.abs(tp.s) * (Math.exp(-tp.age / 1.0) * front + 0.7 * Math.exp(-tp.age / 1.3) * trail);
          glowB += Math.abs(tp.s) * (1 - Math.exp(-tp.age / 0.2)) * Math.exp(-tp.age / 1.2) * trail;

          // жар вокруг пятна
          const hs = spot.s * Math.exp(-(((x - spot.x) ** 2) + ((y - spot.y) ** 2)) / (spot.r * spot.r));
          if (hs > colorHeat) colorHeat = hs;
          }

          // мягкие пределы, как tanh в шейдере
          if (push > 0.0001) {
            const lim = 52 * Math.tanh(push / 52) / push;
            vx *= lim;
            vy *= lim;
          }
          excite = 1.3 * Math.tanh(excite / 1.3);
          if (glowA > 0.8) glowA = 0.8 + (glowA - 0.8) / (1 + 2.5 * (glowA - 0.8));
          if (glowB > 0.8) glowB = 0.8 + (glowB - 0.8) / (1 + 2.5 * (glowB - 0.8));

          // Непрерывное смешивание: море плавно уступает волне.
          // Никакого if-переключения — только линейная интерполяция.
          const wv = Math.min(1, zone * 1.4);
          const crest = Math.min(1, ringMax * 1.5);
          let dens = (1 - wv) * d + wv * crest;
          if (dens < 0) dens = 0;
          if (dens > 1) dens = 1;

          // свечение следа — поверх всего и независимо от просветов
          if (warmth > 0) dens = Math.max(dens, Math.min(1, warmth * 1.15));

          const baseAlpha = dens >= 0.05 ? 0.03 + 0.55 * dens : 0;

          // цвет тоже по гребням и плавно: раньше он заливал весь диск
          const colorAmt = Math.min(1, (glowA + glowB * 0.7) * (0.25 + 0.75 * crest));
          const mixAmt = smoothstep(0.02, 0.34, colorAmt);

          // просветы касаются только моря: волна рисуется всегда
          if (mixAmt <= 0.02 && wv < 0.05 && warmth < 0.02) {
            if (presence < 0.20) continue;
            if (tex < 0.18) continue;
            if (dens < 0.18) continue;
          }
          if (baseAlpha < 0.02 && mixAmt <= 0.0005) continue;
          // ── перебор символов: steps += floor(6 * возбуждение) ──
          const steps = Math.floor(time * 1.2 * glyphSpeed[k] + glyphPace[k] * 0.017 + 6.0 * excite);
          const gi = glyphLook[(lookPick[k] + steps) % glyphLook.length];

          const px = (i * cellW + vx * dpr) | 0;
          const py = (j * cellH + vy * dpr) | 0;

          const put = (color, alpha) => {
            let lvl = Math.round(alpha * (LEVELS - 1));
            if (lvl > LEVELS - 1) lvl = LEVELS - 1;
            if (lvl < 0) lvl = 0;
            if (color > 0 && lvl === 0) return;
            const b = color * LEVELS + lvl;
            let cnt = bufLen[b];
            // бакет растёт по факту, а не до размера всей сетки
            if (cnt >= bufX[b].length) {
              const size = Math.max(256, bufX[b].length * 2);
              const nx = new Int32Array(size); nx.set(bufX[b]); bufX[b] = nx;
              const ny = new Int32Array(size); ny.set(bufY[b]); bufY[b] = ny;
              const ng = new Uint8Array(size); ng.set(bufG[b]); bufG[b] = ng;
            }
            bufX[b][cnt] = px;
            bufY[b][cnt] = py;
            bufG[b][cnt] = gi;
            bufLen[b] = cnt + 1;
          };

          // кроссфейд серый → цвет: цвет приходит, серый ровно на столько уходит
          const grayA = baseAlpha * (1 - mixAmt * 0.92);
          if (grayA >= 0.012) put(0, grayA);

          if (mixAmt > 0.004) {
            const heatMix = Math.min(1, colorHeat);
            const idx = 1 + Math.round(heatMix * (COLORS - 2));
            put(Math.min(idx, COLORS - 1), Math.max(mixAmt, 0.05 * mixAmt));
          }
          total++;
        }
      }

      for (let b = 0; b < bucketCount; b++) {
        const cnt = bufLen[b];
        if (!cnt) continue;
        const X = bufX[b], Y = bufY[b], G = bufG[b];
        const sy = b * cellH;
        for (let q = 0; q < cnt; q++) {
          ctx.drawImage(atlas, G[q] * cellW, sy, cellW, cellH, X[q], Y[q], cellW, cellH);
        }
      }

      if (DEBUG) {
        container.dataset.drawn = String(total);
        container.dataset.grid = cols + 'x' + rows + '@' + cellW;
        container.dataset.taps = String(tapN);
        container.dataset.time = time.toFixed(2);
      }
      return total;
    }

    function frame(now) {
      if (destroyed) return;
      raf = requestAnimationFrame(frame);
      if (!running || document.hidden) return;
      if (now - lastDraw < P.frameMs - 4) return;
      const dt = Math.min((now - lastDraw) / 1000, 0.2) || 0.016;
      lastDraw = now;
      step(dt);
      draw();
      // след не рубим: он должен плавно догореть, как wake в оригинале
      while (trail.length && now - trail[0].t > 1400) trail.shift();
    }

    function tapAt(x, y, strength = 1, ageMs = 0) {
      const nowMs = performance.now();
      if (taps.length > 15) taps.shift();

      // как в оригинале: удар прибавляет 0.2 к импульсу (кап 1.5),
      // а позиция пятна сглаживается к курсору
      const follow = heatImpulse < 0.05 ? 1 : 0.35;
      spot.x += (x - spot.x) * follow;
      spot.y += (y - spot.y) * follow;
      heatImpulse = Math.min(1.5, heatImpulse + 0.2);

      taps.push({ x, y, t0: nowMs - ageMs, s: strength });
      energy = Math.min(1.5, energy + 0.12);
      lastInteract = nowMs;
      if (!running) draw();
    }

    let lastTrailX = -1e9, lastTrailY = -1e9, lastTrailT = -1e9;

    function stirAt(x, y) {
      const nowMs = performance.now();
      const dx = x - lastTrailX, dy = y - lastTrailY;
      const moved = Math.hypot(dx, dy);

      // как move() в оригинале: точка ставится только при реальном движении
      // (>18 px) или если прошло больше 0.25 с — иначе след залипает
      if (moved < 18 && nowMs - lastTrailT < 250) return;

      // сегмент пути: середина, направление и полудлина — как wake в шейдере
      trail.push({
        x: (x + lastTrailX) / 2,
        y: (y + lastTrailY) / 2,
        t: nowMs,
        heat: Math.min(1, moved / 220 + 0.35),
        r2: 170 * 170
      });

      lastTrailX = x;
      lastTrailY = y;
      lastTrailT = nowMs;

      if (trail.length > 24) trail.shift();
      lastInteract = nowMs;
    }

    /* ── старт ── */
    if (!layout()) return null;
    if (INSTANT) container.style.transition = 'none';

    draw();
    container.dataset.ready = '';

    lastDraw = performance.now();
    raf = requestAnimationFrame(frame);

    let rt = 0;
    const ro = new ResizeObserver(() => {
      clearTimeout(rt);
      rt = setTimeout(() => {
        if (destroyed) return;
        if (layout()) lastDraw = 0;
      }, 150);
    });
    ro.observe(container);

    // смена темы → перекрасить атлас
    const themeWatch = new MutationObserver(() => { if (!destroyed) buildAtlas(); });
    themeWatch.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });

    return {
      tapAt,
      stirAt,
      setRunning(v) { running = !!v; if (running) lastDraw = 0; },
      isRunning() { return running; },
      relayout() { if (layout()) { lastDraw = 0; } },
      destroy() {
        destroyed = true;
        cancelAnimationFrame(raf);
        ro.disconnect();
        themeWatch.disconnect();
        canvas.remove();
      }
    };
  }

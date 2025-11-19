document.addEventListener('DOMContentLoaded', function () {
  const carousel = document.querySelector('.hero-carousel');
  if (!carousel) return;

  const slides = Array.from(carousel.querySelectorAll('.hero-slide'));
  let current = 0;
  let autoTimer = null;
  const AUTO_INTERVAL = 5000;

  const dots = Array.from(carousel.querySelectorAll('.hero-dots button'));

  function show(index) {
    index = (index + slides.length) % slides.length;
    slides.forEach((s, i) => {
      s.style.transform = `translateX(${100 * (i - index)}%)`;
      s.classList.toggle('active', i === index);
    });
    dots.forEach((d, i) => d.classList.toggle('active', i === index));
    current = index;
  }

  function next() { show(current + 1); }
  function prev() { show(current - 1); }

  function startAuto() {
    stopAuto();
    autoTimer = setInterval(next, AUTO_INTERVAL);
  }
  function stopAuto() { if (autoTimer) clearInterval(autoTimer); autoTimer = null; }

  // init positions
  slides.forEach((s, i) => { s.style.transition = 'transform 0.45s cubic-bezier(.2,.9,.3,1)'; });
  show(0);
  startAuto();

  // arrow controls
  const left = carousel.querySelector('.hero-prev');
  const right = carousel.querySelector('.hero-next');
  if (left) left.addEventListener('click', () => { prev(); startAuto(); });
  if (right) right.addEventListener('click', () => { next(); startAuto(); });

  // dots click
  dots.forEach((d, i) => {
    d.addEventListener('click', function () { show(i); startAuto(); });
  });

  // keyboard
  window.addEventListener('keydown', function (e) {
    if (e.key === 'ArrowLeft') { prev(); startAuto(); }
    else if (e.key === 'ArrowRight') { next(); startAuto(); }
  });

  // drag (pointer events)
  let pointerStartX = 0;
  let pointerDelta = 0;
  let dragging = false;

  carousel.addEventListener('pointerdown', function (e) {
    dragging = true;
    pointerStartX = e.clientX;
    stopAuto();
    carousel.setPointerCapture(e.pointerId);
  });

  carousel.addEventListener('pointermove', function (e) {
    if (!dragging) return;
    pointerDelta = e.clientX - pointerStartX;
    // tiny translate for slides
    slides.forEach((s, i) => {
      const offset = i - current;
      s.style.transform = `translateX(${100 * offset + (pointerDelta / carousel.clientWidth) * 100}%)`;
    });
  });

  carousel.addEventListener('pointerup', function (e) {
    if (!dragging) return;
    dragging = false;
    carousel.releasePointerCapture(e.pointerId);
    const threshold = carousel.clientWidth * 0.15;
    if (pointerDelta > threshold) {
      prev();
    } else if (pointerDelta < -threshold) {
      next();
    } else {
      show(current);
    }
    pointerDelta = 0;
    startAuto();
  });

  // ensure images/backgrounds are set from data attributes and blurred element
  slides.forEach(s => {
    const img = s.dataset.horizontal || s.dataset.poster;
    const imgEl = s.querySelector('.hero-poster-img');
    const blurEl = s.querySelector('.hero-poster-blur');
    if (imgEl && img) imgEl.src = img;
    if (blurEl && img) blurEl.style.backgroundImage = `url(${img})`;
  });

});

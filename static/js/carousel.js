// Complete Working Carousel Script
document.addEventListener('DOMContentLoaded', function () {
  const carousel = document.querySelector('.hero-carousel');
  if (!carousel) return;

  const slides = Array.from(carousel.querySelectorAll('.hero-slide'));
  const indicators = Array.from(carousel.querySelectorAll('.carousel-indicators button'));
  const prevBtn = carousel.querySelector('.carousel-btn.prev');
  const nextBtn = carousel.querySelector('.carousel-btn.next');
  
  if (slides.length === 0) return;
  
  let current = 0;
  let autoTimer = null;
  let isDragging = false;
  let startX = 0;
  let currentX = 0;
  
  const AUTO_INTERVAL = 10000; // 10 seconds

  function showSlide(index) {
    // Normalize index
    index = (index + slides.length) % slides.length;
    current = index;
    
    // Update slides
    slides.forEach((slide, i) => {
      if (i === index) {
        slide.classList.add('active');
      } else {
        slide.classList.remove('active');
      }
    });
    
    // Update indicators
    indicators.forEach((indicator, i) => {
      if (i === index) {
        indicator.classList.add('active');
      } else {
        indicator.classList.remove('active');
      }
    });
  }

  function nextSlide() {
    showSlide(current + 1);
  }

  function prevSlide() {
    showSlide(current - 1);
  }

  function startAutoplay() {
    stopAutoplay();
    autoTimer = setInterval(nextSlide, AUTO_INTERVAL);
  }

  function stopAutoplay() {
    if (autoTimer) {
      clearInterval(autoTimer);
      autoTimer = null;
    }
  }

  // Initialize
  showSlide(0);
  startAutoplay();

  // Button controls
  if (prevBtn) {
    prevBtn.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      prevSlide();
      startAutoplay();
    });
  }

  if (nextBtn) {
    nextBtn.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      nextSlide();
      startAutoplay();
    });
  }

  // Indicator controls
  indicators.forEach((indicator, index) => {
    indicator.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      showSlide(index);
      startAutoplay();
    });
  });

  // Keyboard navigation
  document.addEventListener('keydown', function(e) {
    if (e.key === 'ArrowLeft') {
      prevSlide();
      startAutoplay();
    } else if (e.key === 'ArrowRight') {
      nextSlide();
      startAutoplay();
    }
  });

  // Touch/Mouse drag support
  carousel.addEventListener('mousedown', handleDragStart, { passive: false });
  carousel.addEventListener('touchstart', handleDragStart, { passive: false });
  carousel.addEventListener('mousemove', handleDragMove, { passive: false });
  carousel.addEventListener('touchmove', handleDragMove, { passive: false });
  carousel.addEventListener('mouseup', handleDragEnd);
  carousel.addEventListener('touchend', handleDragEnd);
  carousel.addEventListener('mouseleave', handleDragEnd);

  function handleDragStart(e) {
    // Don't start drag if clicking on buttons or links
    if (e.target.closest('button, a')) {
      return;
    }
    
    isDragging = true;
    startX = e.type.includes('mouse') ? e.pageX : e.touches[0].pageX;
    currentX = startX;
    stopAutoplay();
    carousel.style.cursor = 'grabbing';
  }

  function handleDragMove(e) {
    if (!isDragging) return;
    e.preventDefault();
    currentX = e.type.includes('mouse') ? e.pageX : e.touches[0].pageX;
  }

  function handleDragEnd(e) {
    if (!isDragging) return;
    isDragging = false;
    carousel.style.cursor = 'grab';
    
    const diff = currentX - startX;
    const threshold = 50; // Minimum drag distance
    
    if (diff > threshold) {
      prevSlide();
    } else if (diff < -threshold) {
      nextSlide();
    }
    
    startAutoplay();
  }

  // Pause on hover
  carousel.addEventListener('mouseenter', stopAutoplay);
  carousel.addEventListener('mouseleave', startAutoplay);
  
  // Pause when tab not visible
  document.addEventListener('visibilitychange', function() {
    if (document.hidden) {
      stopAutoplay();
    } else {
      startAutoplay();
    }
  });
});
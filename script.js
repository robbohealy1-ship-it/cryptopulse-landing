// CryptoPulse Signals - Landing Page Interactions

document.addEventListener('DOMContentLoaded', function() {
    // Navbar scroll effect
    const navbar = document.getElementById('navbar');
    window.addEventListener('scroll', () => {
        if (window.scrollY > 50) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }
    });

    // Mobile menu toggle
    const mobileToggle = document.getElementById('mobileToggle');
    const navLinks = document.getElementById('navLinks');
    
    if (mobileToggle && navLinks) {
        mobileToggle.addEventListener('click', () => {
            navLinks.classList.toggle('active');
            mobileToggle.classList.toggle('active');
        });
        
        // Close menu when clicking a link
        navLinks.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => {
                navLinks.classList.remove('active');
                mobileToggle.classList.remove('active');
            });
        });
    }

    // Animated counter
    const counters = document.querySelectorAll('.stat-number[data-count]');
    
    const animateCounter = (el) => {
        const target = parseInt(el.dataset.count);
        const duration = 2000;
        const increment = target / (duration / 16);
        let current = 0;
        
        const update = () => {
            current += increment;
            if (current < target) {
                el.textContent = Math.floor(current).toLocaleString();
                requestAnimationFrame(update);
            } else {
                el.textContent = target.toLocaleString() + (el.parentElement.querySelector('.stat-label').textContent.includes('%') ? '%' : '+');
            }
        };
        
        update();
    };

    // Intersection Observer for counters
    const counterObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                animateCounter(entry.target);
                counterObserver.unobserve(entry.target);
            }
        });
    }, { threshold: 0.5 });

    counters.forEach(counter => counterObserver.observe(counter));

    // FAQ Accordion
    const faqItems = document.querySelectorAll('.faq-item');
    
    faqItems.forEach(item => {
        const question = item.querySelector('.faq-question');
        
        question.addEventListener('click', () => {
            const isActive = item.classList.contains('active');
            
            // Close all others
            faqItems.forEach(i => i.classList.remove('active'));
            
            // Toggle current
            if (!isActive) {
                item.classList.add('active');
            }
        });
    });

    // Fade in animation on scroll
    const fadeElements = document.querySelectorAll('.feature-card, .pricing-card, .step, .metric');
    
    const fadeObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('fade-in', 'visible');
                fadeObserver.unobserve(entry.target);
            }
        });
    }, { threshold: 0.1, rootMargin: '0px 0px -50px 0px' });

    fadeElements.forEach(el => {
        el.classList.add('fade-in');
        fadeObserver.observe(el);
    });

    // Smooth scroll for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            const href = this.getAttribute('href');
            if (href !== '#') {
                e.preventDefault();
                const target = document.querySelector(href);
                if (target) {
                    target.scrollIntoView({ behavior: 'smooth', block: 'start' });
                }
            }
        });
    });

    // Performance chart animation
    const chartBars = document.querySelectorAll('.bar');
    
    const chartObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                chartBars.forEach((bar, i) => {
                    const originalHeight = bar.style.getPropertyValue('--height');
                    bar.style.setProperty('--height', '0%');
                    setTimeout(() => {
                        bar.style.setProperty('--height', originalHeight);
                    }, i * 100);
                });
                chartObserver.unobserve(entry.target);
            }
        });
    }, { threshold: 0.3 });

    const chartContainer = document.querySelector('.chart-bars');
    if (chartContainer) {
        chartObserver.observe(chartContainer);
    }

    // Parallax effect for hero orbs
    let ticking = false;
    
    window.addEventListener('scroll', () => {
        if (!ticking) {
            requestAnimationFrame(() => {
                const scrollY = window.scrollY;
                const orb1 = document.querySelector('.orb-1');
                const orb2 = document.querySelector('.orb-2');
                
                if (orb1) orb1.style.transform = `translateY(${scrollY * 0.3}px)`;
                if (orb2) orb2.style.transform = `translateY(${scrollY * 0.2}px)`;
                
                ticking = false;
            });
            ticking = true;
        }
    });

    // Add glow effect on pricing card hover
    const pricingCards = document.querySelectorAll('.pricing-card');
    
    pricingCards.forEach(card => {
        card.addEventListener('mouseenter', () => {
            card.style.transition = 'all 0.3s ease';
        });
    });

    // Console welcome message
    console.log('%c CryptoPulse Signals ', 'background: linear-gradient(135deg, #00D4FF, #0066FF); color: white; font-size: 20px; font-weight: bold; padding: 10px 20px; border-radius: 10px;');
    console.log('%c Premium crypto trading signals. Not financial advice. ', 'color: #94A3B8; font-size: 12px;');
});

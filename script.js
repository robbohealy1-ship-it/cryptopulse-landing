// Mobile Menu Toggle
const mobileToggle = document.getElementById('mobileToggle');
const navLinks = document.getElementById('navLinks');

if (mobileToggle && navLinks) {
    mobileToggle.addEventListener('click', () => {
        navLinks.classList.toggle('active');
        mobileToggle.classList.toggle('active');
    });
}

// Navbar Scroll Effect
const navbar = document.getElementById('navbar');

if (navbar) {
    window.addEventListener('scroll', () => {
        if (window.scrollY > 50) {
            navbar.classList.add('scrolled');
        } else {
            navbar.classList.remove('scrolled');
        }
    });
}

// FAQ Accordion
const faqItems = document.querySelectorAll('.faq-item');

faqItems.forEach(item => {
    const question = item.querySelector('.faq-question');
    const answer = item.querySelector('.faq-answer');
    const icon = item.querySelector('.fa-plus');

    if (question && answer) {
        question.addEventListener('click', () => {
            const isOpen = answer.style.maxHeight && answer.style.maxHeight !== '0px';

            // Close all others
            faqItems.forEach(otherItem => {
                const otherAnswer = otherItem.querySelector('.faq-answer');
                const otherIcon = otherItem.querySelector('.fa-plus');
                if (otherAnswer && otherAnswer !== answer) {
                    otherAnswer.style.maxHeight = '0px';
                    otherAnswer.style.padding = '0 24px';
                    if (otherIcon) otherIcon.classList.remove('rotate');
                }
            });

            // Toggle current
            if (isOpen) {
                answer.style.maxHeight = '0px';
                answer.style.padding = '0 24px';
                if (icon) icon.classList.remove('rotate');
            } else {
                answer.style.maxHeight = answer.scrollHeight + 48 + 'px';
                answer.style.padding = '0 24px 24px';
                if (icon) icon.classList.add('rotate');
            }
        });
    }
});

// Smooth Scroll for Anchor Links
document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function (e) {
        const href = this.getAttribute('href');
        if (href !== '#') {
            e.preventDefault();
            const target = document.querySelector(href);
            if (target) {
                const navHeight = navbar ? navbar.offsetHeight : 0;
                const targetPosition = target.getBoundingClientRect().top + window.pageYOffset - navHeight - 20;
                window.scrollTo({
                    top: targetPosition,
                    behavior: 'smooth'
                });
                // Close mobile menu if open
                if (navLinks) navLinks.classList.remove('active');
                if (mobileToggle) mobileToggle.classList.remove('active');
            }
        }
    });
});

// Stat Counter Animation
const statNumbers = document.querySelectorAll('.stat-number');

const animateCounter = (element) => {
    const target = parseInt(element.getAttribute('data-count')) || 0;
    const duration = 2000;
    const start = 0;
    const startTime = performance.now();

    const updateCounter = (currentTime) => {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const easeOut = 1 - Math.pow(1 - progress, 3);
        const current = Math.floor(start + (target - start) * easeOut);
        element.textContent = current + (element.textContent.includes('%') ? '%' : element.textContent.includes('R') ? 'R' : '');

        if (progress < 1) {
            requestAnimationFrame(updateCounter);
        } else {
            element.textContent = target;
        }
    };

    requestAnimationFrame(updateCounter);
};

// Intersection Observer for Stat Animation
const observerOptions = {
    threshold: 0.3,
    rootMargin: '0px 0px -50px 0px'
};

const statObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            animateCounter(entry.target);
            statObserver.unobserve(entry.target);
        }
    });
}, observerOptions);

statNumbers.forEach(stat => statObserver.observe(stat));

// Feature Card Reveal on Scroll
const featureCards = document.querySelectorAll('.feature-card');

const cardObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateY(0)';
            cardObserver.unobserve(entry.target);
        }
    });
}, { threshold: 0.1 });

featureCards.forEach((card, index) => {
    card.style.opacity = '0';
    card.style.transform = 'translateY(30px)';
    card.style.transition = `opacity 0.5s ease ${index * 0.1}s, transform 0.5s ease ${index * 0.1}s`;
    cardObserver.observe(card);
});

// Pricing Card Reveal
const pricingCards = document.querySelectorAll('.pricing-card');

const pricingObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateY(0)';
            pricingObserver.unobserve(entry.target);
        }
    });
}, { threshold: 0.1 });

pricingCards.forEach((card, index) => {
    card.style.opacity = '0';
    card.style.transform = 'translateY(30px)';
    card.style.transition = `opacity 0.5s ease ${index * 0.15}s, transform 0.5s ease ${index * 0.15}s`;
    pricingObserver.observe(card);
});

// Step Reveal Animation
const steps = document.querySelectorAll('.step');

const stepObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateX(0)';
            stepObserver.unobserve(entry.target);
        }
    });
}, { threshold: 0.2 });

steps.forEach((step, index) => {
    step.style.opacity = '0';
    step.style.transform = index % 2 === 0 ? 'translateX(-30px)' : 'translateX(30px)';
    step.style.transition = `opacity 0.6s ease ${index * 0.2}s, transform 0.6s ease ${index * 0.2}s`;
    stepObserver.observe(step);
});

// Performance Chart Bar Animation
const chartBars = document.querySelectorAll('.bar');

const chartObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            const bar = entry.target;
            const height = bar.style.getPropertyValue('--height');
            bar.style.setProperty('--final-height', height);
            bar.style.setProperty('--height', '0%');
            setTimeout(() => {
                bar.style.setProperty('--height', height);
            }, 100);
            chartObserver.unobserve(bar);
        }
    });
}, { threshold: 0.3 });

chartBars.forEach(bar => chartObserver.observe(bar));

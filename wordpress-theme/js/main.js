/**
 * ChuckysCarnage Theme JavaScript
 */

(function() {
    'use strict';

    // Theme toggle functionality
    const themeToggle = document.querySelector('.theme-toggle');
    const html = document.documentElement;
    
    // Check for saved theme preference or system preference
    function initTheme() {
        const savedTheme = localStorage.getItem('theme');
        const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        
        if (savedTheme) {
            html.setAttribute('data-theme', savedTheme);
        } else if (systemPrefersDark) {
            html.setAttribute('data-theme', 'dark');
        } else {
            html.setAttribute('data-theme', 'light');
        }
    }
    
    // Toggle theme
    function toggleTheme() {
        const currentTheme = html.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        
        html.setAttribute('data-theme', newTheme);
        localStorage.setItem('theme', newTheme);
        
        // Update toggle icon if present
        if (themeToggle) {
            const icon = themeToggle.querySelector('svg');
            if (icon) {
                icon.innerHTML = newTheme === 'dark' 
                    ? '<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>'
                    : '<circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>';
            }
        }
    }
    
    if (themeToggle) {
        themeToggle.addEventListener('click', toggleTheme);
    }
    
    // Initialize theme on load
    initTheme();
    
    // Back to top button
    const backToTop = document.querySelector('.back-to-top');
    
    function handleScroll() {
        if (backToTop) {
            if (window.scrollY > 300) {
                backToTop.classList.add('visible');
            } else {
                backToTop.classList.remove('visible');
            }
        }
    }
    
    function scrollToTop() {
        window.scrollTo({
            top: 0,
            behavior: 'smooth'
        });
    }
    
    if (backToTop) {
        backToTop.addEventListener('click', scrollToTop);
    }
    
    window.addEventListener('scroll', handleScroll);
    
    // Mobile menu toggle
    const mobileMenuToggle = document.querySelector('.mobile-menu-toggle');
    const mainNavigation = document.querySelector('.main-navigation');
    
    if (mobileMenuToggle && mainNavigation) {
        mobileMenuToggle.addEventListener('click', function() {
            mainNavigation.classList.toggle('active');
            mobileMenuToggle.classList.toggle('active');
        });
    }
    
    // Article card hover effects
    const articleCards = document.querySelectorAll('.article-card');
    
    articleCards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-4px)';
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0)';
        });
    });
    
    // Newsletter form handling
    const newsletterForms = document.querySelectorAll('.newsletter-form');
    
    newsletterForms.forEach(form => {
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const email = this.querySelector('input[type="email"]').value;
            const button = this.querySelector('button[type="submit"]');
            
            if (email) {
                button.textContent = 'Subscribing...';
                button.disabled = true;
                
                // Simulate API call
                setTimeout(() => {
                    button.textContent = 'Subscribed!';
                    button.style.background = '#10b981';
                    
                    setTimeout(() => {
                        button.textContent = 'Subscribe';
                        button.style.background = '';
                        button.disabled = false;
                        this.reset();
                    }, 2000);
                }, 1000);
            }
        });
    });
    
    // Contact form handling
    const contactForm = document.querySelector('.contact-form');
    
    if (contactForm) {
        contactForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const button = this.querySelector('button[type="submit"]');
            const formData = new FormData(this);
            
            button.textContent = 'Sending...';
            button.disabled = true;
            
            // Simulate form submission
            setTimeout(() => {
                button.textContent = 'Message Sent!';
                button.style.background = '#10b981';
                
                setTimeout(() => {
                    button.textContent = 'Send Message';
                    button.style.background = '';
                    button.disabled = false;
                    this.reset();
                }, 2000);
            }, 1000);
        });
    }
    
    // Lazy load images
    if ('IntersectionObserver' in window) {
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    if (img.dataset.src) {
                        img.src = img.dataset.src;
                        img.removeAttribute('data-src');
                        observer.unobserve(img);
                    }
                }
            });
        });
        
        document.querySelectorAll('img[data-src]').forEach(img => {
            imageObserver.observe(img);
        });
    }
    
    // Smooth scroll for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                e.preventDefault();
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
    
    // Add loading state to images
    document.querySelectorAll('img').forEach(img => {
        img.addEventListener('load', function() {
            this.classList.add('loaded');
        });
        
        if (img.complete) {
            img.classList.add('loaded');
        }
    });
    
})();

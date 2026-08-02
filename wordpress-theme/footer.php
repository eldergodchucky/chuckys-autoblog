<footer class="site-footer">
    <div class="container">
        <div class="footer-content">
            <div class="footer-section">
                <h3>About ChuckysCarnage</h3>
                <p style="color: var(--text-secondary); line-height: 1.6;">
                    ChuckysCarnage is an independent technology publication covering artificial intelligence, cybersecurity, gaming, science, software, mobile technology, and emerging innovations. We explain not only what is happening, but why it matters.
                </p>
            </div>
            
            <div class="footer-section">
                <h3>Quick Links</h3>
                <ul class="footer-links">
                    <li><a href="<?php echo esc_url(home_url('/about')); ?>">About</a></li>
                    <li><a href="<?php echo esc_url(home_url('/contact')); ?>">Contact</a></li>
                    <li><a href="<?php echo esc_url(home_url('/privacy-policy')); ?>">Privacy</a></li>
                    <li><a href="<?php echo esc_url(home_url('/disclaimer')); ?>">Disclaimer</a></li>
                </ul>
            </div>
            
            <div class="footer-section">
                <h3>Policies</h3>
                <ul class="footer-links">
                    <li><a href="<?php echo esc_url(home_url('/editorial-policy')); ?>">Editorial Policy</a></li>
                    <li><a href="<?php echo esc_url(home_url('/affiliate-disclosure')); ?>">Affiliate Disclosure</a></li>
                    <li><a href="<?php echo esc_url(home_url('/ai-policy')); ?>">AI Policy</a></li>
                    <li><a href="<?php echo esc_url(home_url('/cookie-policy')); ?>">Cookie Policy</a></li>
                </ul>
            </div>
            
            <div class="footer-section">
                <h3>Connect</h3>
                <ul class="footer-links">
                    <li><a href="#">Twitter/X</a></li>
                    <li><a href="#">LinkedIn</a></li>
                    <li><a href="#">RSS Feed</a></li>
                    <li><a href="<?php echo esc_url(home_url('/sitemap.xml')); ?>">Sitemap</a></li>
                </ul>
            </div>
        </div>
        
        <div class="footer-bottom">
            <p>&copy; <?php echo date('Y'); ?> ChuckysCarnage. All rights reserved.</p>
        </div>
    </div>
</footer>

<button class="back-to-top" aria-label="Back to top">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="24" height="24">
        <polyline points="18 15 12 9 6 15"/>
    </svg>
</button>

<?php wp_footer(); ?>
</body>
</html>

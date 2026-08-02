<?php
/**
 * Template Name: Contact Page
 */

get_header();
?>

<main class="main-content">
    <div class="container">
        <div class="page-content">
            <h1 class="page-title">Contact</h1>
            
            <div class="contact-intro">
                <p>Have a question, suggestion, correction, partnership opportunity, or business inquiry?</p>
                
                <p>We'd love to hear from you.</p>
                
                <p>Reach out using the contact form below or connect through our official social media channels.</p>
                
                <p>We aim to respond as quickly as possible.</p>
            </div>
            
            <div class="contact-form-wrapper">
                <form class="contact-form" method="post" action="">
                    <?php if (isset($_POST['submitted']) && $_POST['submitted'] == '1') : ?>
                        <div class="form-success">
                            <p>Thank you for your message! We'll get back to you soon.</p>
                        </div>
                    <?php else : ?>
                        <div class="form-group">
                            <label for="contact-name" class="form-label">Name</label>
                            <input type="text" id="contact-name" name="contact-name" class="form-input" required>
                        </div>
                        
                        <div class="form-group">
                            <label for="contact-email" class="form-label">Email</label>
                            <input type="email" id="contact-email" name="contact-email" class="form-input" required>
                        </div>
                        
                        <div class="form-group">
                            <label for="contact-subject" class="form-label">Subject</label>
                            <input type="text" id="contact-subject" name="contact-subject" class="form-input" required>
                        </div>
                        
                        <div class="form-group">
                            <label for="contact-message" class="form-label">Message</label>
                            <textarea id="contact-message" name="contact-message" class="form-textarea" required></textarea>
                        </div>
                        
                        <input type="hidden" name="submitted" value="1">
                        <button type="submit" class="btn btn-primary">Send Message</button>
                    <?php endif; ?>
                </form>
            </div>
            
            <div class="contact-social">
                <h3>Connect With Us</h3>
                <div class="social-links">
                    <a href="#" class="social-link">
                        <svg viewBox="0 0 24 24" fill="currentColor" width="24" height="24">
                            <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
                        </svg>
                        Follow on X
                    </a>
                    <a href="#" class="social-link">
                        <svg viewBox="0 0 24 24" fill="currentColor" width="24" height="24">
                            <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
                        </svg>
                        LinkedIn
                    </a>
                    <a href="<?php echo esc_url(home_url('/feed/')); ?>" class="social-link">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="24" height="24">
                            <path d="M4 11a9 9 0 0 1 9 9"/>
                            <path d="M4 4a16 16 0 0 1 16 16"/>
                            <circle cx="5" cy="19" r="1"/>
                        </svg>
                        RSS Feed
                    </a>
                </div>
            </div>
        </div>
    </div>
</main>

<?php
get_footer();

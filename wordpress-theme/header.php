<!DOCTYPE html>
<html <?php language_attributes(); ?>>
<head>
    <meta charset="<?php bloginfo('charset'); ?>">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="profile" href="https://gmpg.org/xfn/11">
    <?php wp_head(); ?>
</head>
<body <?php body_class(); ?>>
<?php wp_body_open(); ?>

<header class="site-header">
    <div class="container header-content">
        <a href="<?php echo esc_url(home_url('/')); ?>" class="site-logo">
            <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="2" y="2" width="36" height="36" rx="4" stroke="#00e5ff" stroke-width="2"/>
                <text x="20" y="28" text-anchor="middle" fill="#00e5ff" font-family="Arial, sans-serif" font-weight="bold" font-size="16">CC</text>
            </svg>
            <span class="site-logo-text">ChuckysCarnage</span>
        </a>
        
        <nav class="main-navigation">
            <?php
            wp_nav_menu(array(
                'theme_location' => 'primary',
                'container' => false,
                'items_wrap' => '%3$s',
                'fallback_cb' => false,
            ));
            ?>
        </nav>
        
        <button class="theme-toggle" aria-label="Toggle theme">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20">
                <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>
            </svg>
        </button>
        
        <button class="mobile-menu-toggle" aria-label="Toggle menu">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="24" height="24">
                <line x1="3" y1="12" x2="21" y2="12"/>
                <line x1="3" y1="6" x2="21" y2="6"/>
                <line x1="3" y1="18" x2="21" y2="18"/>
            </svg>
        </button>
    </div>
</header>

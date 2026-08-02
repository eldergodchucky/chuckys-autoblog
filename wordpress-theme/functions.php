<?php
/**
 * ChuckysCarnage Premium Theme Functions
 */

// Theme setup
function chuckyscarnage_setup() {
    // Add theme support
    add_theme_support('title-tag');
    add_theme_support('post-thumbnails');
    add_theme_support('automatic-feed-links');
    add_theme_support('html5', array(
        'search-form',
        'comment-form',
        'comment-list',
        'gallery',
        'caption',
    ));
    
    // Register navigation menus
    register_nav_menus(array(
        'primary' => __('Primary Navigation', 'chuckyscarnage'),
        'footer' => __('Footer Navigation', 'chuckyscarnage'),
    ));
    
    // Set content width
    $GLOBALS['content_width'] = 1200;
}
add_action('after_setup_theme', 'chuckyscarnage_setup');

// Enqueue scripts and styles
function chuckyscarnage_scripts() {
    wp_enqueue_style('chuckyscarnage-style', get_stylesheet_uri(), array(), '1.0.0');
    wp_enqueue_style('chuckyscarnage-custom', get_template_directory_uri() . '/custom-style.css', array(), '1.0.0');
    
    // Enqueue Google Fonts (Inter)
    wp_enqueue_style('chuckyscarnage-fonts', 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap', array(), null);
    
    wp_enqueue_script('chuckyscarnage-main', get_template_directory_uri() . '/js/main.js', array(), '1.0.0', true);
    
    if (is_singular() && comments_open() && get_option('thread_comments')) {
        wp_enqueue_script('comment-reply');
    }
}
add_action('wp_enqueue_scripts', 'chuckyscarnage_scripts');

// Theme customizer
function chuckyscarnage_customize_register($wp_customize) {
    // Dark/Light mode default
    $wp_customize->add_setting('theme_mode', array(
        'default' => 'dark',
        'sanitize_callback' => 'sanitize_text_field',
    ));
    
    $wp_customize->add_control('theme_mode', array(
        'label' => __('Default Theme Mode', 'chuckyscarnage'),
        'section' => 'colors',
        'type' => 'select',
        'choices' => array(
            'dark' => __('Dark', 'chuckyscarnage'),
            'light' => __('Light', 'chuckyscarnage'),
        ),
    ));
    
    // Primary color
    $wp_customize->add_setting('primary_color', array(
        'default' => '#00e5ff',
        'sanitize_callback' => 'sanitize_hex_color',
    ));
    
    $wp_customize->add_control(new WP_Customize_Color_Control($wp_customize, 'primary_color', array(
        'label' => __('Primary Color', 'chuckyscarnage'),
        'section' => 'colors',
    )));
}
add_action('customize_register', 'chuckyscarnage_customize_register');

// Estimated reading time
function chuckyscarnage_reading_time() {
    $content = get_post_field('post_content', get_the_ID());
    $word_count = str_word_count(strip_tags($content));
    $reading_time = ceil($word_count / 200);
    
    return sprintf(
        _n('%d min read', '%d min read', $reading_time, 'chuckyscarnage'),
        $reading_time
    );
}

// View count (using post meta)
function chuckyscarnage_get_view_count() {
    $post_id = get_the_ID();
    $count = get_post_meta($post_id, 'view_count', true);
    return $count ? intval($count) : 0;
}

function chuckyscarnage_increment_view_count() {
    if (!is_single()) return;
    
    $post_id = get_the_ID();
    $count = chuckyscarnage_get_view_count();
    update_post_meta($post_id, 'view_count', $count + 1);
}
add_action('wp_head', 'chuckyscarnage_increment_view_count');

// Remove Uncategorized category
function chuckyscarnage_remove_uncategorized() {
    $uncat = get_category_by_slug('uncategorized');
    if ($uncat) {
        wp_delete_term($uncat->term_id, 'category');
    }
}
add_action('init', 'chuckyscarnage_remove_uncategorized');

// Limit tags to 5
function chuckyscarnage_limit_tags($term_ids) {
    if (count($term_ids) > 5) {
        return array_slice($term_ids, 0, 5);
    }
    return $term_ids;
}
add_filter('wp_get_object_terms', 'chuckyscarnage_limit_tags', 10, 3);

// Custom excerpt length
function chuckyscarnage_excerpt_length($length) {
    return 30;
}
add_filter('excerpt_length', 'chuckyscarnage_excerpt_length');

// Custom excerpt more
function chuckyscarnage_excerpt_more($more) {
    return '...';
}
add_filter('excerpt_more', 'chuckyscarnage_excerpt_more');

// Add category to body class
function chuckyscarnage_body_classes($classes) {
    if (is_single()) {
        $categories = get_the_category();
        if ($categories) {
            $classes[] = 'category-' . $categories[0]->slug;
        }
    }
    return $classes;
}
add_filter('body_class', 'chuckyscarnage_body_classes');

// Disable emoji scripts
function chuckyscarnage_disable_emojis() {
    remove_action('wp_head', 'print_emoji_detection_script', 7);
    remove_action('wp_print_styles', 'print_emoji_styles');
}
add_action('init', 'chuckyscarnage_disable_emojis');

// Remove WordPress version
remove_action('wp_head', 'wp_generator');

// Add meta description
function chuckyscarnage_meta_description() {
    if (is_single()) {
        $excerpt = get_the_excerpt();
        echo '<meta name="description" content="' . esc_attr($excerpt) . '">' . "\n";
    }
}
add_action('wp_head', 'chuckyscarnage_meta_description');

// Open Graph tags
function chuckyscarnage_og_tags() {
    if (is_single()) {
        global $post;
        echo '<meta property="og:title" content="' . esc_attr(get_the_title()) . '">' . "\n";
        echo '<meta property="og:description" content="' . esc_attr(get_the_excerpt()) . '">' . "\n";
        echo '<meta property="og:url" content="' . esc_url(get_permalink()) . '">' . "\n";
        echo '<meta property="og:type" content="article">' . "\n";
        
        if (has_post_thumbnail()) {
            echo '<meta property="og:image" content="' . esc_url(get_the_post_thumbnail_url($post->ID, 'large')) . '">' . "\n";
        }
    }
}
add_action('wp_head', 'chuckyscarnage_og_tags');

// Schema markup
function chuckyscarnage_schema_markup() {
    if (is_single()) {
        global $post;
        $schema = array(
            '@context' => 'https://schema.org',
            '@type' => 'NewsArticle',
            'headline' => get_the_title(),
            'description' => get_the_excerpt(),
            'author' => array(
                '@type' => 'Organization',
                'name' => 'ChuckysCarnage'
            ),
            'publisher' => array(
                '@type' => 'Organization',
                'name' => 'ChuckysCarnage',
                'logo' => array(
                    '@type' => 'ImageObject',
                    'url' => get_template_directory_uri() . '/images/logo.png'
                )
            ),
            'mainEntityOfPage' => array(
                '@type' => 'WebPage',
                '@id' => get_permalink()
            )
        );
        
        echo '<script type="application/ld+json">' . json_encode($schema) . '</script>' . "\n";
    }
}
add_action('wp_head', 'chuckyscarnage_schema_markup');

// Related posts
function chuckyscarnage_get_related_posts($post_id, $limit = 3) {
    $categories = wp_get_post_categories($post_id);
    
    $args = array(
        'post_type' => 'post',
        'post_status' => 'publish',
        'posts_per_page' => $limit,
        'post__not_in' => array($post_id),
        'category__in' => $categories,
        'orderby' => 'rand',
    );
    
    return get_posts($args);
}

// Newsletter shortcode
function chuckyscarnage_newsletter_shortcode() {
    ob_start();
    ?>
    <div class="newsletter-section">
        <h3 class="newsletter-title">Stay Ahead of Tomorrow</h3>
        <p class="newsletter-description">Receive the latest articles covering AI, cybersecurity, gaming, science, software, and technology delivered directly to your inbox.</p>
        <form class="newsletter-form" action="#" method="post">
            <input type="email" class="newsletter-input" placeholder="Enter your email" required>
            <button type="submit" class="btn btn-primary">Subscribe</button>
        </form>
    </div>
    <?php
    return ob_get_clean();
}
add_shortcode('newsletter', 'chuckyscarnage_newsletter_shortcode');

// XML Sitemap Generation
function chuckyscarnage_sitemap_rewrite_rule() {
    add_rewrite_rule('^sitemap\.xml$', 'index.php?sitemap=1', 'top');
}
add_action('init', 'chuckyscarnage_sitemap_rewrite_rule');

function chuckyscarnage_sitemap_query_vars($query_vars) {
    $query_vars[] = 'sitemap';
    return $query_vars;
}
add_filter('query_vars', 'chuckyscarnage_sitemap_query_vars');

function chuckyscarnage_generate_sitemap() {
    if (!get_query_var('sitemap')) {
        return;
    }
    
    header('Content-Type: application/xml; charset=utf-8');
    echo '<?xml version="1.0" encoding="UTF-8"?>';
    echo '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">';
    
    // Homepage
    echo '<url>';
    echo '<loc>' . esc_url(home_url('/')) . '</loc>';
    echo '<lastmod>' . date('c') . '</lastmod>';
    echo '<changefreq>daily</changefreq>';
    echo '<priority>1.0</priority>';
    echo '</url>';
    
    // Posts
    $posts = get_posts(array(
        'post_type' => 'post',
        'post_status' => 'publish',
        'numberposts' => -1,
    ));
    
    foreach ($posts as $post) {
        echo '<url>';
        echo '<loc>' . esc_url(get_permalink($post->ID)) . '</loc>';
        echo '<lastmod>' . date('c', strtotime($post->post_modified)) . '</lastmod>';
        echo '<changefreq>weekly</changefreq>';
        echo '<priority>0.8</priority>';
        echo '</url>';
    }
    
    // Pages
    $pages = get_pages(array(
        'post_status' => 'publish',
    ));
    
    foreach ($pages as $page) {
        echo '<url>';
        echo '<loc>' . esc_url(get_permalink($page->ID)) . '</loc>';
        echo '<lastmod>' . date('c', strtotime($page->post_modified)) . '</lastmod>';
        echo '<changefreq>monthly</changefreq>';
        echo '<priority>0.6</priority>';
        echo '</url>';
    }
    
    // Categories
    $categories = get_categories(array(
        'hide_empty' => true,
    ));
    
    foreach ($categories as $category) {
        echo '<url>';
        echo '<loc>' . esc_url(get_category_link($category->term_id)) . '</loc>';
        echo '<changefreq>weekly</changefreq>';
        echo '<priority>0.5</priority>';
        echo '</url>';
    }
    
    // Tags
    $tags = get_tags(array(
        'hide_empty' => true,
    ));
    
    foreach ($tags as $tag) {
        echo '<url>';
        echo '<loc>' . esc_url(get_tag_link($tag->term_id)) . '</loc>';
        echo '<changefreq>weekly</changefreq>';
        echo '<priority>0.4</priority>';
        echo '</url>';
    }
    
    echo '</urlset>';
    exit;
}
add_action('template_redirect', 'chuckyscarnage_generate_sitemap');

// Share count tracking
function chuckyscarnage_get_share_count($post_id = null) {
    if (!$post_id) {
        $post_id = get_the_ID();
    }
    
    $share_count = get_post_meta($post_id, 'share_count', true);
    return $share_count ? intval($share_count) : 0;
}

function chuckyscarnage_increment_share_count($post_id = null) {
    if (!$post_id) {
        $post_id = get_the_ID();
    }
    
    $count = chuckyscarnage_get_share_count($post_id);
    update_post_meta($post_id, 'share_count', $count + 1);
}

// Core Web Vitals optimization
function chuckyscarnage_performance_optimization() {
    // Preload critical resources
    echo '<link rel="preconnect" href="https://fonts.googleapis.com">' . "\n";
    echo '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>' . "\n";
    echo '<link rel="dns-prefetch" href="//chuckyscarnage.tech.blog">' . "\n";
    
    // Defer non-critical JavaScript
    echo '<script>
    document.addEventListener("DOMContentLoaded", function() {
        // Defer non-critical scripts
        var scripts = document.querySelectorAll("script[data-defer]");
        scripts.forEach(function(script) {
            script.defer = true;
        });
    });
    </script>' . "\n";
}
add_action('wp_head', 'chuckyscarnage_performance_optimization', 1);

// Remove unnecessary WordPress bloat
function chuckyscarnage_remove_bloat() {
    // Remove emoji scripts
    remove_action('wp_head', 'print_emoji_detection_script', 7);
    remove_action('wp_print_styles', 'print_emoji_styles');
    
    // Remove WordPress version
    remove_action('wp_head', 'wp_generator');
    
    // Remove RSD link
    remove_action('wp_head', 'rsd_link');
    
    // Remove wlwmanifest link
    remove_action('wp_head', 'wlwmanifest_link');
    
    // Remove shortlink
    remove_action('wp_head', 'wp_shortlink_wp_head');
    
    // Remove adjacent posts links
    remove_action('wp_head', 'adjacent_posts_rel_link_wp_head');
}
add_action('init', 'chuckyscarnage_remove_bloat');

// Lazy load images with native loading attribute
function chuckyscarnage_lazy_load_images($content) {
    if (!is_admin() && !is_feed()) {
        $content = preg_replace('/<img([^>]+)src=/i', '<img$1loading="lazy" src=', $content);
    }
    return $content;
}
add_filter('the_content', 'chuckyscarnage_lazy_load_images', 10);

// AJAX handler for share tracking
function chuckyscarnage_track_share_ajax() {
    $post_id = isset($_POST['post_id']) ? intval($_POST['post_id']) : 0;
    
    if ($post_id > 0) {
        $count = chuckyscarnage_get_share_count($post_id);
        update_post_meta($post_id, 'share_count', $count + 1);
        wp_send_json_success(array('count' => $count + 1));
    }
    
    wp_send_json_error();
}
add_action('wp_ajax_track_share', 'chuckyscarnage_track_share_ajax');
add_action('wp_ajax_nopriv_track_share', 'chuckyscarnage_track_share_ajax');

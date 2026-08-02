<?php
/**
 * XML Sitemap Generation
 */

// Add sitemap rewrite rule
function chuckyscarnage_sitemap_rewrite_rule() {
    add_rewrite_rule('^sitemap\.xml$', 'index.php?sitemap=1', 'top');
}
add_action('init', 'chuckyscarnage_sitemap_rewrite_rule');

// Add sitemap query var
function chuckyscarnage_sitemap_query_vars($query_vars) {
    $query_vars[] = 'sitemap';
    return $query_vars;
}
add_filter('query_vars', 'chuckyscarnage_sitemap_query_vars');

// Generate sitemap content
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

// Flush rewrite rules on theme activation
function chuckyscarnage_flush_rewrite_rules() {
    chuckyscarnage_sitemap_rewrite_rule();
    flush_rewrite_rules();
}
register_activation_hook(__FILE__, 'chuckyscarnage_flush_rewrite_rules');

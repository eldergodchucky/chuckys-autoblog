<?php
/**
 * Article Card Template Part
 */

$classes = array('article-card');
if (is_front_page() && $wp_query->current_post === 0) {
    $classes[] = 'featured-card';
}
?>

<article <?php post_class($classes); ?>>
    <?php if (has_post_thumbnail()) : ?>
        <a href="<?php the_permalink(); ?>" class="article-card-image-link">
            <img src="<?php the_post_thumbnail_url('medium'); ?>" 
                 alt="<?php echo esc_attr(get_the_title()); ?>" 
                 class="article-card-image"
                 loading="lazy">
        </a>
    <?php else : ?>
        <div class="article-card-image-placeholder"></div>
    <?php endif; ?>
    
    <div class="article-card-content">
        <?php
        $categories = get_the_category();
        if ($categories) :
            $category = $categories[0];
        ?>
            <span class="article-card-category">
                <?php echo esc_html($category->name); ?>
            </span>
        <?php endif; ?>
        
        <h3 class="article-card-title">
            <a href="<?php the_permalink(); ?>">
                <?php the_title(); ?>
            </a>
        </h3>
        
        <p class="article-card-excerpt">
            <?php echo get_the_excerpt(); ?>
        </p>
        
        <div class="article-card-meta">
            <div class="article-card-meta-item">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                    <circle cx="12" cy="12" r="10"/>
                    <polyline points="12 6 12 12 16 14"/>
                </svg>
                <?php echo chuckyscarnage_reading_time(); ?>
            </div>
            <div class="article-card-meta-item">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                    <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
                    <line x1="16" y1="2" x2="16" y2="6"/>
                    <line x1="8" y1="2" x2="8" y2="6"/>
                    <line x1="3" y1="10" x2="21" y2="10"/>
                </svg>
                <?php echo get_the_date('M j, Y'); ?>
            </div>
            <div class="article-card-meta-item">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="14" height="14">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                    <circle cx="12" cy="12" r="3"/>
                </svg>
                <?php echo chuckyscarnage_get_view_count(); ?>
            </div>
        </div>
    </div>
</article>

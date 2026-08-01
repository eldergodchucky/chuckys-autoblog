<?php
/**
 * Single Post Template
 */

get_header();
?>

<main class="main-content">
    <?php while (have_posts()) : the_post(); ?>
        
        <!-- Breadcrumb Navigation -->
        <nav class="breadcrumb container">
            <a href="<?php echo esc_url(home_url('/')); ?>">Home</a>
            <span class="breadcrumb-separator">/</span>
            <?php
            $categories = get_the_category();
            if ($categories) :
                $category = $categories[0];
            ?>
                <a href="<?php echo esc_url(get_category_link($category->term_id)); ?>">
                    <?php echo esc_html($category->name); ?>
                </a>
                <span class="breadcrumb-separator">/</span>
            <?php endif; ?>
            <span><?php the_title(); ?></span>
        </nav>

        <article class="article-single">
            <div class="container">
                <div class="article-header">
                    <?php
                    $categories = get_the_category();
                    if ($categories) :
                        $category = $categories[0];
                    ?>
                        <span class="article-category-badge">
                            <?php echo esc_html($category->name); ?>
                        </span>
                    <?php endif; ?>
                    
                    <h1 class="article-title"><?php the_title(); ?></h1>
                    
                    <div class="article-meta">
                        <div class="article-meta-item">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                                <circle cx="12" cy="12" r="10"/>
                                <polyline points="12 6 12 12 16 14"/>
                            </svg>
                            <?php echo chuckyscarnage_reading_time(); ?>
                        </div>
                        <div class="article-meta-item">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                                <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
                                <line x1="16" y1="2" x2="16" y2="6"/>
                                <line x1="8" y1="2" x2="8" y2="6"/>
                                <line x1="3" y1="10" x2="21" y2="10"/>
                            </svg>
                            <?php echo get_the_date(); ?>
                        </div>
                        <div class="article-meta-item">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                                <circle cx="12" cy="12" r="3"/>
                            </svg>
                            <?php echo chuckyscarnage_get_view_count(); ?> views
                        </div>
                        <div class="article-meta-item">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                                <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/>
                            </svg>
                            <?php echo get_comments_number(); ?> comments
                        </div>
                    </div>
                </div>

                <?php if (has_post_thumbnail()) : ?>
                    <div class="article-featured-image">
                        <?php the_post_thumbnail('large'); ?>
                    </div>
                <?php endif; ?>

                <div class="article-content">
                    <?php the_content(); ?>
                </div>

                <!-- Author Biography -->
                <div class="author-bio">
                    <div class="author-avatar">
                        <?php echo get_avatar(get_the_author_meta('ID'), 64); ?>
                    </div>
                    <div class="author-info">
                        <h4 class="author-name"><?php the_author(); ?></h4>
                        <p class="author-description"><?php the_author_meta('description'); ?></p>
                    </div>
                </div>

                <!-- Social Sharing Buttons -->
                <div class="social-sharing">
                    <h4>Share this article</h4>
                    <div class="share-buttons">
                        <a href="<?php echo esc_url('https://twitter.com/intent/tweet?text=' . urlencode(get_the_title()) . '&url=' . urlencode(get_permalink())); ?>" target="_blank" rel="noopener" class="share-button share-twitter">
                            <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
                                <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z"/>
                            </svg>
                            Share on X
                        </a>
                        <a href="<?php echo esc_url('https://www.linkedin.com/sharing/share-offsite/?url=' . urlencode(get_permalink())); ?>" target="_blank" rel="noopener" class="share-button share-linkedin">
                            <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
                                <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/>
                            </svg>
                            Share on LinkedIn
                        </a>
                        <a href="<?php echo esc_url('https://www.facebook.com/sharer/sharer.php?u=' . urlencode(get_permalink())); ?>" target="_blank" rel="noopener" class="share-button share-facebook">
                            <svg viewBox="0 0 24 24" fill="currentColor" width="20" height="20">
                                <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z"/>
                            </svg>
                            Share on Facebook
                        </a>
                        <a href="mailto:?subject=<?php echo urlencode(get_the_title()); ?>&body=<?php echo urlencode(get_permalink()); ?>" class="share-button share-email">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20">
                                <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/>
                                <polyline points="22,6 12,13 2,6"/>
                            </svg>
                            Share via Email
                        </a>
                    </div>
                </div>

                <!-- Related Articles -->
                <?php
                $related_posts = chuckyscarnage_get_related_posts(get_the_ID(), 3);
                if ($related_posts) :
                ?>
                <div class="related-articles">
                    <h3>Related Articles</h3>
                    <div class="article-grid">
                        <?php foreach ($related_posts as $post) : setup_postdata($post); ?>
                            <?php get_template_part('template-parts/content', 'card'); ?>
                        ><?php endforeach; wp_reset_postdata(); ?>
                    </div>
                </div>
                <?php endif; ?>

                <!-- Previous/Next Navigation -->
                <div class="post-navigation">
                    <?php
                    $prev_post = get_previous_post();
                    $next_post = get_next_post();
                    ?>
                    
                    <?php if ($prev_post) : ?>
                        <div class="nav-prev">
                            <a href="<?php echo esc_url(get_permalink($prev_post->ID)); ?>">
                                <span class="nav-label">Previous Article</span>
                                <span class="nav-title"><?php echo esc_html($prev_post->post_title); ?></span>
                            </a>
                        </div>
                    <?php endif; ?>
                    
                    <?php if ($next_post) : ?>
                        <div class="nav-next">
                            <a href="<?php echo esc_url(get_permalink($next_post->ID)); ?>">
                                <span class="nav-label">Next Article</span>
                                <span class="nav-title"><?php echo esc_html($next_post->post_title); ?></span>
                            </a>
                        </div>
                    <?php endif; ?>
                </div>

                <!-- Comments -->
                <?php if (comments_open() || get_comments_number()) : ?>
                    <div class="comments-section">
                        <?php comments_template(); ?>
                    </div>
                <?php endif; ?>
            </div>
        </article>
        
    <?php endwhile; ?>
</main>

<?php
get_footer();

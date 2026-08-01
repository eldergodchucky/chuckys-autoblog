<?php
/**
 * Front Page Template - Magazine Style Layout
 */

get_header();
?>

<main class="main-content">
    <!-- Hero Section -->
    <section class="hero-section">
        <div class="container">
            <h1 class="hero-title">Technology Explained Beyond the Headlines</h1>
            <p class="hero-description">
                ChuckysCarnage explores artificial intelligence, cybersecurity, science, gaming, space, software, mobile technology, and the innovations shaping tomorrow. Every article goes beyond the news to explain why it matters, what happens next, and how it affects everyday people.
            </p>
            <div class="hero-buttons">
                <a href="#latest" class="btn btn-primary">Start Reading</a>
                <a href="#latest" class="btn btn-secondary">Latest News</a>
            </div>
        </div>
    </section>

    <!-- Featured Stories -->
    < section class="section">
        <div class="container">
            <h2 class="section-title">Featured Stories</h2>
            <div class="article-grid">
                <?php
                $featured_args = array(
                    'post_type' => 'post',
                    'post_status' => 'publish',
                    'posts_per_page' => 3,
                    'meta_query' => array(
                        array(
                            'key' => '_featured',
                            'value' => '1',
                            'compare' => '='
                        )
                    ),
                    'orderby' => 'date',
                    'order' => 'DESC'
                );
                
                $featured_query = new WP_Query($featured_args);
                
                if ($featured_query->have_posts()) :
                    while ($featured_query->have_posts()) : $featured_query->the_post();
                        get_template_part('template-parts/content', 'card');
                    endwhile;
                    wp_reset_postdata();
                else :
                    // Fallback to latest posts if no featured posts
                    $latest_args = array(
                        'post_type' => 'post',
                        'post_status' => 'publish',
                        'posts_per_page' => 3,
                        'orderby' => 'date',
                        'order' => 'DESC'
                    );
                    $latest_query = new WP_Query($latest_args);
                    
                    if ($latest_query->have_posts()) :
                        while ($latest_query->have_posts()) : $latest_query->the_post();
                            get_template_part('template-parts/content', 'card');
                        endwhile;
                        wp_reset_postdata();
                    endif;
                endif;
                ?>
            </div>
        </div>
    </section>

    <!-- Trending Articles -->
    <section class="section">
        <div class="container">
            <h2 class="section-title">Trending Articles</h2>
            <div class="article-grid">
                <?php
                $trending_args = array(
                    'post_type' => 'post',
                    'post_status' => 'publish',
                    'posts_per_page' => 4,
                    'meta_key' => 'view_count',
                    'orderby' => 'meta_value_num',
                    'order' => 'DESC',
                    'date_query' => array(
                        array(
                            'after' => '1 week ago'
                        )
                    )
                );
                
                $trending_query = new WP_Query($trending_args);
                
                if ($trending_query->have_posts()) :
                    while ($trending_query->have_posts()) : $trending_query->the_post();
                        get_template_part('template-parts/content', 'card');
                    endwhile;
                    wp_reset_postdata();
                endif;
                ?>
            </div>
        </div>
    </section>

    <!-- Category Sections -->
    <?php
    $categories = array('ai', 'cybersecurity', 'gaming', 'science', 'mobile', 'software', 'space');
    
    foreach ($categories as $category_slug) :
        $category = get_category_by_slug($category_slug);
        
        if ($category) :
    ?>
    <section class="section">
        <div class="container">
            <h2 class="section-title"><?php echo esc_html($category->name); ?></h2>
            <div class="article-grid">
                <?php
                $cat_args = array(
                    'post_type' => 'post',
                    'post_status' => 'publish',
                    'posts_per_page' => 3,
                    'category_name' => $category_slug,
                    'orderby' => 'date',
                    'order' => 'DESC'
                );
                
                $cat_query = new WP_Query($cat_args);
                
                if ($cat_query->have_posts()) :
                    while ($cat_query->have_posts()) : $cat_query->the_post();
                        get_template_part('template-parts/content', 'card');
                    endwhile;
                    wp_reset_postdata();
                endif;
                ?>
            </div>
        </div>
    </section>
    <?php
        endif;
    endforeach;
    ?>

    <!-- Opinion -->
    <section class="section">
        <div class="container">
            <h2 class="section-title">Opinion</h2>
            <div class="article-grid">
                <?php
                $opinion_args = array(
                    'post_type' => 'post',
                    'post_status' => 'publish',
                    'posts_per_page' => 3,
                    'tag' => 'opinion',
                    'orderby' => 'date',
                    'order' => 'DESC'
                );
                
                $opinion_query = new WP_Query($opinion_args);
                
                if ($opinion_query->have_posts()) :
                    while ($opinion_query->have_posts()) : $opinion_query->the_post();
                        get_template_part('template-parts/content', 'card');
                    endwhile;
                    wp_reset_postdata();
                endif;
                ?>
            </div>
        </div>
    </section>

    <!-- Reviews -->
    <section class="section">
        <div class="container">
            <h2 class="section-title">Reviews</h2>
            <div class="article-grid">
                <?php
                $reviews_args = array(
                    'post_type' => 'post',
                    'post_status' => 'publish',
                    'posts_per_page' => 3,
                    'tag' => 'review',
                    'orderby' => 'date',
                    'order' => 'DESC'
                );
                
                $reviews_query = new WP_Query($reviews_args);
                
                if ($reviews_query->have_posts()) :
                    while ($reviews_query->have_posts()) : $reviews_query->the_post();
                        get_template_part('template-parts/content', 'card');
                    endwhile;
                    wp_reset_postdata();
                endif;
                ?>
            </div>
        </div>
    </section>

    <!-- Guides -->
    <section class="section">
        <div class="container">
            <h2 class="section-title">Guides</h2>
            <div class="article-grid">
                <?php
                $guides_args = array(
                    'post_type' => 'post',
                    'post_status' => 'publish',
                    'posts_per_page' => 3,
                    'tag' => 'guide',
                    'orderby' => 'date',
                    'order' => 'DESC'
                );
                
                $guides_query = new WP_Query($guides_args);
                
                if ($guides_query->have_posts()) :
                    while ($guides_query->have_posts()) : $guides_query->the_post();
                        get_template_part('template-parts/content', 'card');
                    endwhile;
                    wp_reset_postdata();
                endif;
                ?>
            </div>
        </div>
    </section>

    <!-- Latest Articles -->
    <section class="section" id="latest">
        <div class="container">
            <h2 class="section-title">Latest Articles</h2>
            <div class="article-grid">
                <?php
                $latest_args = array(
                    'post_type' => 'post',
                    'post_status' => 'publish',
                    'posts_per_page' => 6,
                    'orderby' => 'date',
                    'order' => 'DESC'
                );
                
                $latest_query = new WP_Query($latest_args);
                
                if ($latest_query->have_posts()) :
                    while ($latest_query->have_posts()) : $latest_query->the_post();
                        get_template_part('template-parts/content', 'card');
                    endwhile;
                    wp_reset_postdata();
                endif;
                ?>
            </div>
        </div>
    </section>

    <!-- Newsletter Signup -->
    <section class="section">
        <div class="container">
            <?php echo do_shortcode('[newsletter]'); ?>
        </div>
    </section>

    <!-- Popular Tags -->
    <section class="section">
        <div class="container">
            <h2 class="section-title">Popular Tags</h2>
            <div class="tags-cloud">
                <?php
                $tags = get_tags(array(
                    'orderby' => 'count',
                    'order' => 'DESC',
                    'number' => 20
                ));
                
                foreach ($tags as $tag) :
                    $tag_link = get_tag_link($tag->term_id);
                ?>
                <a href="<?php echo esc_url($tag_link); ?>" class="tag-badge">
                    <?php echo esc_html($tag->name); ?>
                </a>
                <?php endforeach; ?>
            </div>
        </div>
    </section>
</main>

<?php
get_footer();

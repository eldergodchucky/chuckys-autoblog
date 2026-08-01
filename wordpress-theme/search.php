<?php
/**
 * Search Results Template with Advanced Filters
 */

get_header();
?>

<main class="main-content">
    <div class="container">
        <div class="search-page">
            <h1 class="page-title">Search Results</h1>
            
            <!-- Advanced Search Form -->
            <div class="search-filters">
                <form class="advanced-search-form" method="get" action="<?php echo esc_url(home_url('/')); ?>">
                    <div class="search-input-wrapper">
                        <input type="text" 
                               name="s" 
                               class="search-input" 
                               placeholder="Search articles..." 
                               value="<?php echo esc_attr(get_search_query()); ?>"
                               required>
                        <button type="submit" class="search-submit">
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20">
                                <circle cx="11" cy="11" r="8"/>
                                <line x1="21" y1="21" x2="16.65" y2="16.65"/>
                            </svg>
                        </button>
                    </div>
                    
                    <div class="filter-options">
                        <div class="filter-group">
                            <label for="filter-category">Category</label>
                            <select id="filter-category" name="cat">
                                <option value="">All Categories</option>
                                <?php
                                $categories = get_categories(array('hide_empty' => true));
                                foreach ($categories as $category) :
                                    $selected = isset($_GET['cat']) && $_GET['cat'] == $category->term_id ? 'selected' : '';
                                ?>
                                    <option value="<?php echo esc_attr($category->term_id); ?>" <?php echo $selected; ?>>
                                        <?php echo esc_html($category->name); ?>
                                    </option>
                                <?php endforeach; ?>
                            </select>
                        </div>
                        
                        <div class="filter-group">
                            <label for="filter-tag">Tag</label>
                            <select id="filter-tag" name="tag">
                                <option value="">All Tags</option>
                                <?php
                                $tags = get_tags(array('hide_empty' => true));
                                foreach ($tags as $tag) :
                                    $selected = isset($_GET['tag']) && $_GET['tag'] == $tag->slug ? 'selected' : '';
                                ?>
                                    <option value="<?php echo esc_attr($tag->slug); ?>" <?php echo $selected; ?>>
                                        <?php echo esc_html($tag->name); ?>
                                    </option>
                                <?php endforeach; ?>
                            </select>
                        </div>
                        
                        <div class="filter-group">
                            <label for="filter-date">Date</label>
                            <select id="filter-date" name="date">
                                <option value="">Any Time</option>
                                <option value="today" <?php echo isset($_GET['date']) && $_GET['date'] == 'today' ? 'selected' : ''; ?>>Today</option>
                                <option value="week" <?php echo isset($_GET['date']) && $_GET['date'] == 'week' ? 'selected' : ''; ?>>This Week</option>
                                <option value="month" <?php echo isset($_GET['date']) && $_GET['date'] == 'month' ? 'selected' : ''; ?>>This Month</option>
                                <option value="year" <?php echo isset($_GET['date']) && $_GET['date'] == 'year' ? 'selected' : ''; ?>>This Year</option>
                            </select>
                        </div>
                        
                        <div class="filter-group">
                            <label for="filter-sort">Sort By</label>
                            <select id="filter-sort" name="sort">
                                <option value="relevance" <?php echo isset($_GET['sort']) && $_GET['sort'] == 'relevance' ? 'selected' : ''; ?>>Relevance</option>
                                <option value="date" <?php echo isset($_GET['sort']) && $_GET['sort'] == 'date' ? 'selected' : ''; ?>>Date</option>
                                <option value="views" <?php echo isset($_GET['sort']) && $_GET['sort'] == 'views' ? 'selected' : ''; ?>>Most Viewed</option>
                            </select>
                        </div>
                        
                        <button type="submit" class="btn btn-primary">Apply Filters</button>
                        <a href="<?php echo esc_url(home_url('/')); ?>" class="btn btn-secondary">Reset</a>
                    </div>
                </form>
            </div>
            
            <!-- Search Results -->
            <div class="search-results">
                <?php if (have_posts()) : ?>
                    <p class="results-count">
                        Found <?php echo $wp_query->found_posts; ?> result(s) for "<?php echo esc_html(get_search_query()); ?>"
                    </p>
                    
                    <div class="article-grid">
                        <?php while (have_posts()) : the_post(); ?>
                            <?php get_template_part('template-parts/content', 'card'); ?>
                        <?php endwhile; ?>
                    </div>
                    
                    <!-- Pagination -->
                    <div class="pagination">
                        <?php
                        echo paginate_links(array(
                            'total' => $wp_query->max_num_pages,
                            'prev_text' => '← Previous',
                            'next_text' => 'Next →',
                        ));
                        ?>
                    </div>
                    
                <?php else : ?>
                    <div class="no-results">
                        <h2>No Results Found</h2>
                        <p>We couldn't find any articles matching your search criteria.</p>
                        <p>Try:</p>
                        <ul>
                            <li>Using different keywords</li>
                            <li>Checking your spelling</li>
                            <li>Removing some filters</li>
                            <li>Browsing our categories</li>
                        </ul>
                        <a href="<?php echo esc_url(home_url('/')); ?>" class="btn btn-primary">Return to Homepage</a>
                    </div>
                <?php endif; ?>
            </div>
        </div>
    </div>
</main>

<?php
get_footer();

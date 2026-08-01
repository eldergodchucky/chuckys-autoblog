(function () {
  'use strict';

  var API = 'https://public-api.wordpress.com/rest/v1.1/sites/chuckyscarnage.tech.blog';
  var POOL_FIELDS = 'ID,slug,title,date,modified,URL,short_URL,excerpt,content,author,categories,tags,featured_image,like_count,discussion,sticky';
  var LIGHT_FIELDS = 'ID,title,date,categories,tags';
  var poolPromise = null;
  var lightPoolPromise = null;

  function fetchPages(fields) {
    return apiGet('/posts/?number=100&page=1&fields=' + fields)
      .then(function (r1) {
        return apiGet('/posts/?number=100&page=2&fields=' + fields).then(function (r2) {
          return (r1.posts || []).concat(r2.posts || []);
        });
      });
  }

  var GRADIENTS = [
    ['#21d8ff', '#7c5cff'],
    ['#0ea5e9', '#6366f1'],
    ['#22d3ee', '#a855f7'],
    ['#38bdf8', '#8b5cf6'],
    ['#67e8f9', '#7c5cff'],
    ['#14b8a6', '#6366f1'],
    ['#60a5fa', '#a855f7'],
    ['#2dd4bf', '#22d3ee']
  ];

  function apiGet(path) {
    return fetch(API + path).then(function (res) {
      if (!res.ok) throw new Error('API ' + res.status);
      return res.json();
    });
  }

  function postsPool(force) {
    if (poolPromise && !force) return poolPromise;
    poolPromise = fetchPages(POOL_FIELDS).catch(function (err) {
      poolPromise = null;
      throw err;
    });
    return poolPromise;
  }

  function lightPool(force) {
    if (lightPoolPromise && !force) return lightPoolPromise;
    lightPoolPromise = fetchPages(LIGHT_FIELDS).catch(function (err) {
      lightPoolPromise = null;
      throw err;
    });
    return lightPoolPromise;
  }

  function stripHtml(html) {
    var div = document.createElement('div');
    div.innerHTML = html || '';
    return (div.textContent || '').replace(/\s+/g, ' ').trim();
  }

  function excerptText(post) {
    var text = stripHtml(post.excerpt || post.content);
    return text.replace(/\[&hellip;\]/g, '').replace(/â€¦$/g, '').trim();
  }

  function excerptShort(post, max) {
    var text = excerptText(post);
    if (text.length <= (max || 200)) return text;
    return text.slice(0, (max || 200)).replace(/\s+\S*$/, '') + '…';
  }

  function cleanContent(html) {
    var div = document.createElement('div');
    div.innerHTML = html || '';
    var imgs = div.querySelectorAll('img');
    for (var i = 0; i < imgs.length; i++) {
      var src = imgs[i].getAttribute('src') || '';
      var host = '';
      try { host = new URL(src).hostname; } catch (e) { host = ''; }
      var bad = !host ||
        host.indexOf('internal.cloudapp.net') > -1 ||
        host.indexOf('local') > -1 ||
        host.indexOf('.local') > -1 ||
        /^[\d.]+$/.test(host);
      if (bad) imgs[i].parentNode.removeChild(imgs[i]);
    }
    return div.innerHTML;
  }

  function readingTime(post) {
    var words = stripHtml(post.content || '').split(/\s+/).filter(Boolean).length;
    return Math.max(1, Math.round(words / 200));
  }

  function formatDate(iso) {
    if (!iso) return '';
    return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }

  function hashOf(str) {
    var h = 0;
    for (var i = 0; i < str.length; i++) h = ((h << 5) - h + str.charCodeAt(i)) | 0;
    return Math.abs(h);
  }

  function gradientFor(str) {
    return GRADIENTS[hashOf(str || 'x') % GRADIENTS.length];
  }

  function categoryNames(post) {
    return (post.categories && Object.keys(post.categories)) || [];
  }

  function tagNames(post) {
    if (!post.tags) return [];
    return Object.values(post.tags).map(function (t) { return t && t.name ? t.name : ''; }).filter(Boolean);
  }

  function commentCount(post) {
    return (post.discussion && post.discussion.comment_count) || 0;
  }

  function authorName(post) {
    return (post.author && post.author.name) || 'ChuckysCarnage';
  }

  function avatarUrl(post) {
    if (post.author && post.author.avatar_URL) return post.author.avatar_URL.split('?')[0] + '?s=96';
    return 'assets/logo.svg';
  }

  function postUrl(post) {
    return 'article.html?post=' + post.ID;
  }

  function mediaBlock(post) {
    if (post.featured_image) {
      return '<img class="card-media" src="' + post.featured_image + '" alt="" loading="lazy">';
    }
    var g = gradientFor(post.title);
    return '<div class="card-media art" style="background:linear-gradient(135deg,' + g[0] + ', ' + g[1] + ')" aria-hidden="true"></div>';
  }

  function metaLine(post) {
    var parts = [readingTime(post) + ' min read', formatDate(post.date)];
    if (post.like_count) parts.push(post.like_count + ' likes');
    var cc = commentCount(post);
    if (cc) parts.push(cc + ' comment' + (cc === 1 ? '' : 's'));
    return '<div class="meta">' + parts.map(function (p) { return '<span>' + p + '</span>'; }).join('') + '</div>';
  }

  function cardMarkup(post, opts) {
    opts = opts || {};
    var cats = categoryNames(post);
    var badge = opts.badge || (cats.length ? cats[0] : 'Technology');
    var media = opts.noMedia ? '' : mediaBlock(post);
    var text = opts.text || excerptShort(post);
    return (
      '<article class="card" data-card data-category="' + cats.join(' ').toLowerCase() + '" data-tags="' + tagNames(post).join(' ').toLowerCase() + '" data-date="' + (post.date || '').slice(0, 10) + '">' +
      media +
      '<div class="card-body">' +
      '<span class="badge">' + badge + '</span>' +
      '<h3><a href="' + postUrl(post) + '">' + (post.title || 'Untitled') + '</a></h3>' +
      (opts.noMeta ? '' : metaLine(post)) +
      (text ? '<p>' + text + '</p>' : '') +
      '<div class="card-footer"><span>' + authorName(post) + '</span><a href="' + postUrl(post) + '">Read more</a></div>' +
      '</div>' +
      '</article>'
    );
  }

  function skeletonCards(n, noMedia) {
    var out = '';
    for (var i = 0; i < n; i++) {
      out += '<article class="card skeleton-card">' +
        (noMedia ? '' : '<div class="card-media skeleton"></div>') +
        '<div class="card-body">' +
        '<span class="badge skeleton badge-skeleton"></span>' +
        '<div class="line skeleton"></div><div class="line skeleton short"></div>' +
        '<div class="line skeleton tiny"></div>' +
        '</div></article>';
    }
    return out;
  }

  function fill(selector, html) {
    var el = document.querySelector(selector);
    if (el) el.innerHTML = html;
  }

  function renderHomepage(posts) {
    var recent = posts.slice();
    recent.sort(function (a, b) { return new Date(b.date) - new Date(a.date); });

    var featured = recent.slice(0, 3);
    fill('#featured-grid', featured.map(function (p) { return cardMarkup(p); }).join(''));

    var trending = recent.slice(3, 7);
    fill('#trending-grid', trending.map(function (p) {
      return cardMarkup(p, { noMedia: true, text: excerptShort(p, 120) });
    }).join(''));

    var catCounts = {};
    posts.forEach(function (p) {
      categoryNames(p).forEach(function (c) {
        var key = c.toLowerCase();
        if (key === 'info' || key === 'tech' || key === 'science') catCounts[key] = (catCounts[key] || 0) + 1;
      });
    });
    var order = Object.keys(catCounts).sort(function (a, b) { return catCounts[b] - catCounts[a]; });
    var titles = { tech: 'Technology', science: 'Science', info: 'Info & Analysis' };
    order.slice(0, 3).forEach(function (cat, idx) {
      var slot = '#cat-grid-' + (idx + 1);
      var header = document.querySelector('[data-cat-title="' + cat + '"]');
      if (header) header.textContent = titles[cat] || cat;
      var list = posts.filter(function (p) {
        return categoryNames(p).some(function (c) { return c.toLowerCase() === cat; });
      }).slice(0, 3);
      fill(slot, list.map(function (p) { return cardMarkup(p); }).join(''));
      var link = document.querySelector('[data-cat-more="' + cat + '"]');
      if (link) {
        link.addEventListener('click', function (e) {
          e.preventDefault();
          setFilter({ category: cat, scroll: true });
        });
      }
    });

    fill('#latest', renderLatest(posts));
    fill('#tag-cloud', renderTagCloud(posts));
    initFilters(posts);
  }

  function applySearchTo(cards, query) {
    var q = (query || '').toLowerCase();
    return cards.filter(function (p) {
      if (!q) return true;
      return (p.title || '').toLowerCase().indexOf(q) > -1 || excerptText(p).toLowerCase().indexOf(q) > -1;
    });
  }

  function renderLatest(posts) {
    var state = window.__ccFilter || {};
    var q = state.search || '';
    var cat = (state.category || '').toLowerCase();
    var tag = (state.tag || '').toLowerCase();
    var range = state.range || '';
    var now = Date.now();
    var rangeMs = { '24h': 864e5, '7d': 6048e5, '30d': 2592e6 };

    var list = applySearchTo(posts, q).filter(function (p) {
      var okCat = !cat || categoryNames(p).some(function (c) { return c.toLowerCase() === cat; });
      var okTag = !tag || tagNames(p).some(function (t) { return t.toLowerCase() === tag; });
      var okRange = !rangeMs[range] || (now - new Date(p.date).getTime()) <= rangeMs[range];
      return okCat && okTag && okRange;
    }).slice(0, 12);

    if (!list.length) {
      return '<div class="feed-error"><p>No stories match those filters.</p></div>';
    }
    return list.map(function (p) { return cardMarkup(p); }).join('');
  }

  function initFilters(posts) {
    var search = document.querySelector('[data-search]');
    var category = document.querySelector('[data-category]');
    var tag = document.querySelector('[data-tag]');
    var range = document.querySelector('[data-range]');

    if (category) {
      var counts = {};
      posts.forEach(function (p) { categoryNames(p).forEach(function (c) { counts[c] = (counts[c] || 0) + 1; }); });
      var options = Object.keys(counts).sort().map(function (c) {
        return '<option value="' + c.toLowerCase() + '">' + c + '</option>';
      }).join('');
      category.insertAdjacentHTML('beforeend', options);
    }

    if (tag) {
      var tagCounts = {};
      posts.forEach(function (p) { tagNames(p).forEach(function (t) { tagCounts[t] = (tagCounts[t] || 0) + 1; }); });
      var tagOptions = Object.keys(tagCounts)
        .filter(function (t) { return t.length > 2 && tagCounts[t] > 1; })
        .sort(function (a, b) { return tagCounts[b] - tagCounts[a]; })
        .slice(0, 24)
        .map(function (t) { return '<option value="' + t.toLowerCase() + '">' + t + '</option>'; })
        .join('');
      tag.insertAdjacentHTML('beforeend', tagOptions);
    }

    var refresh = function () {
      window.__ccFilter = {
        search: search ? search.value : '',
        category: category ? category.value : '',
        tag: tag ? tag.value : '',
        range: range ? range.value : ''
      };
      fill('#latest', renderLatest(posts));
    };

    [search, category, tag, range].forEach(function (el) {
      if (el) el.addEventListener('input', refresh);
      if (el && el.tagName === 'SELECT') el.addEventListener('change', refresh);
    });

    var params = new URLSearchParams(window.location.search);
    var q = params.get('q');
    if (q && search) { search.value = q; }
    var c = params.get('cat');
    if (c && category) category.value = c;
    var t = params.get('tag');
    if (t && tag) tag.value = t;
    if (q || c || t) refresh();
  }

  function setFilter(next) {
    window.__ccFilter = Object.assign({}, window.__ccFilter || {}, { category: next.category || '', search: next.search || '' });
    var category = document.querySelector('[data-category]');
    var search = document.querySelector('[data-search]');
    if (category && next.category) category.value = next.category;
    if (search && next.search) search.value = next.search;
    if (next.category) {
      fill('#latest', renderLatest(window.__ccPosts || []));
    }
    if (next.scroll) {
      var el = document.getElementById('latest');
      if (el) el.scrollIntoView({ behavior: 'smooth' });
    }
  }

  function renderTagCloud(posts) {
    var counts = {};
    posts.forEach(function (p) { tagNames(p).forEach(function (t) { counts[t] = (counts[t] || 0) + 1; }); });
    var top = Object.keys(counts)
      .filter(function (t) { return t.length > 2 && counts[t] > 1; })
      .sort(function (a, b) { return counts[b] - counts[a]; })
      .slice(0, 24);
    return top.map(function (t) {
      return '<a href="#latest" data-tag-link="' + t.toLowerCase() + '">' + t + '</a>';
    }).join('');
  }

  function initHome() {
    ['#featured-grid', '#trending-grid', '#cat-grid-1', '#cat-grid-2', '#cat-grid-3', '#latest'].forEach(function (s) {
      fill(s, skeletonCards(3, s === '#trending-grid'));
    });

    postsPool()
      .then(function (posts) {
        window.__ccPosts = posts;
        renderHomepage(posts);
      })
      .catch(function (err) {
        ['#featured-grid', '#trending-grid', '#cat-grid-1', '#cat-grid-2', '#cat-grid-3', '#latest', '#tag-cloud'].forEach(function (s) {
          fill(s, '<div class="feed-error"><p>Could not reach the ChuckysCarnage feed.</p></div>');
        });
        if (window.console) console.error(err);
      });
  }

  function renderArticle(post) {
    var cats = categoryNames(post);
    var primary = cats.length ? cats[0] : 'Technology';

    document.title = (post.title || 'Article') + ' | ChuckysCarnage';
    var desc = document.querySelector('meta[name="description"]');
    if (desc) desc.setAttribute('content', excerptText(post).slice(0, 155));

    fill('#article-breadcrumb', '<a href="index.html">Home</a> / <span>' + primary + '</span> / <span>' + (post.title || '') + '</span>');
    fill('#article-badge', '<span class="badge">' + primary + '</span>');
    fill('#article-title', post.title || '');
    fill('#article-lead', excerptText(post));
    fill('#article-meta', metaLine(post));
    fill('#article-media', post.featured_image
      ? '<img class="article-hero-img" src="' + post.featured_image + '" alt="" loading="lazy">'
      : '');

    var body = document.getElementById('article-body');
    if (body) body.innerHTML = cleanContent(post.content) || '<p>No content available.</p>';

    fill('#article-author', '<img class="avatar" src="' + avatarUrl(post) + '" alt="">' +
      '<div><strong>' + authorName(post) + '</strong><span class="muted">Staff writer, ChuckysCarnage</span></div>');

    var shareLinks = [
      ['X', 'https://twitter.com/intent/tweet?text=' + encodeURIComponent(post.title) + '&url=' + encodeURIComponent(post.URL)],
      ['LinkedIn', 'https://www.linkedin.com/sharing/share-offsite/?url=' + encodeURIComponent(post.URL)],
      ['Facebook', 'https://www.facebook.com/sharer/sharer.php?u=' + encodeURIComponent(post.URL)],
      ['WhatsApp', 'https://wa.me/?text=' + encodeURIComponent(post.title + ' ' + post.URL)],
      ['Email', 'mailto:?subject=' + encodeURIComponent(post.title) + '&body=' + encodeURIComponent(post.URL)]
    ];
    fill('#article-share', shareLinks.map(function (s) {
      return '<a href="' + s[1] + '" target="_blank" rel="noopener nofollow">' + s[0] + '</a>';
    }).join(''));

    var cc = commentCount(post);
    fill('#article-comments', '<p>' + (cc ? cc + ' comments so far.' : 'No comments yet.') + '</p>' +
      '<p><a class="btn btn-primary" href="' + post.URL + '#comments" target="_blank" rel="noopener">Join the discussion on the live post</a></p>');

    return lightPool().then(function (pool) {
      var sorted = pool.slice().sort(function (a, b) { return new Date(b.date) - new Date(a.date); });
      var idx = sorted.findIndex(function (p) { return p.ID === post.ID; });

      var older = idx > 0 ? sorted[idx - 1] : null;
      var newer = idx >= 0 && idx < sorted.length - 1 ? sorted[idx + 1] : null;

      fill('#article-prev', older
        ? '<h3>Previous</h3><p><a href="' + postUrl(older) + '">' + older.title + '</a></p>'
        : '<h3>Previous</h3><p class="muted">This is the newest story.</p>');
      fill('#article-next', newer
        ? '<h3>Next</h3><p><a href="' + postUrl(newer) + '">' + newer.title + '</a></p>'
        : '<h3>Next</h3><p class="muted">You are up to date.</p>');

      var related = sorted
        .filter(function (p) { return p.ID !== post.ID && categoryNames(p).some(function (c) { return c === primary; }); })
        .slice(0, 3);
      if (!related.length) {
        related = sorted.filter(function (p) { return p.ID !== post.ID; }).slice(0, 3);
      }
      fill('#article-related', '<ul>' + related.map(function (p) {
        return '<li><a href="' + postUrl(p) + '">' + p.title + '</a></li>';
      }).join('') + '</ul>');

      var tagCounts = {};
      pool.forEach(function (p) { tagNames(p).forEach(function (t) { tagCounts[t] = (tagCounts[t] || 0) + 1; }); });
      var topTags = Object.keys(tagCounts)
        .filter(function (t) { return t.length > 2 && tagCounts[t] > 1; })
        .sort(function (a, b) { return tagCounts[b] - tagCounts[a]; })
        .slice(0, 12);
      fill('#article-tags', topTags.map(function (t) {
        return '<a href="index.html?tag=' + encodeURIComponent(t.toLowerCase()) + '">' + t + '</a>';
      }).join(''));
    });
  }

  function initArticle() {
    var params = new URLSearchParams(window.location.search);
    var id = params.get('post');
    if (!id) {
      window.location.href = 'index.html';
      return;
    }

    apiGet('/posts/' + encodeURIComponent(id) + '?fields=' + POOL_FIELDS)
      .then(function (post) {
        if (!post || !post.ID) throw new Error('Post not found');
        renderArticle(post);
      })
      .catch(function (err) {
        var shell = document.querySelector('.article-shell');
        if (shell) {
          shell.innerHTML = '<div class="feed-error"><p>This story could not be loaded.</p><a class="btn btn-primary" href="index.html">Back to homepage</a></div>';
        }
        if (window.console) console.error(err);
      });
  }

  function initTheme() {
    var storageKey = 'cc-theme';
    var prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    var saved = localStorage.getItem(storageKey);
    var initial = saved || (prefersDark ? 'dark' : 'light');
    document.documentElement.setAttribute('data-theme', initial);

    var button = document.querySelector('[data-theme-toggle]');
    if (button) {
      button.textContent = initial === 'dark' ? 'Light mode' : 'Dark mode';
      button.addEventListener('click', function () {
        var current = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', current);
        localStorage.setItem(storageKey, current);
        button.textContent = current === 'dark' ? 'Light mode' : 'Dark mode';
      });
    }
  }

  function initBackToTop() {
    var btn = document.querySelector('.back-to-top');
    if (!btn) return;
    window.addEventListener('scroll', function () {
      if (window.scrollY > 500) btn.classList.add('visible'); else btn.classList.remove('visible');
    });
    btn.addEventListener('click', function () { window.scrollTo({ top: 0, behavior: 'smooth' }); });
  }

  function initNewsletter() {
    var form = document.querySelector('[data-newsletter]');
    if (!form) return;
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      form.innerHTML = '<p class="newsletter-ok">Thanks for subscribing. New stories will land in your inbox.</p>';
    });
  }

  document.addEventListener('click', function (e) {
    var link = e.target.closest('[data-tag-link]');
    if (link) {
      e.preventDefault();
      var tag = link.getAttribute('data-tag-link');
      window.__ccFilter = Object.assign({}, window.__ccFilter || {}, { tag: tag, search: '' });
      var tagSelect = document.querySelector('[data-tag]');
      if (tagSelect) tagSelect.value = tag;
      fill('#latest', renderLatest(window.__ccPosts || []));
      var el = document.getElementById('latest');
      if (el) el.scrollIntoView({ behavior: 'smooth' });
    }
  });

  initTheme();
  initBackToTop();
  initNewsletter();

  if (document.getElementById('latest')) {
    initHome();
  }
  if (document.getElementById('article-body')) {
    initArticle();
  }
})();

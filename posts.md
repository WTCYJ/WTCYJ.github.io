---
layout: default
title: Posts
permalink: /posts/
---

<section class="section">

  <div class="section-header">
    <span class="section-label">all posts</span>
    <div class="section-line"></div>
    <span class="post-tag tag-teal" id="result-count">{{ site.posts | size }}</span>
  </div>

  <div class="search-box search-box--lg">
    <span class="search-prompt">/</span>
    <input type="search" id="q" class="search-input" placeholder="제목 · 카테고리 · 태그 · 요약으로 검색" aria-label="글 검색" autocomplete="off">
    <button type="button" class="search-go" id="q-clear" aria-label="검색어 지우기" hidden>✕</button>
  </div>

  <div class="filter-bar">
    <button type="button" class="filter-btn active" data-filter="all" data-color="all">all</button>
    {% for c in site.data.categories %}
      <button type="button" class="filter-btn" data-filter="{{ c.key }}" data-color="{{ c.color }}">{{ c.name }}</button>
    {% endfor %}
  </div>

  {% assign atlas_posts = site.posts | where: "series", "Android Security Concept Atlas" | sort: "date" | reverse %}
  {% assign regular_posts = site.posts | where_exp: "post", "post.series != 'Android Security Concept Atlas'" %}
  {% assign ordered_posts = atlas_posts | concat: regular_posts %}

  <div class="posts-list" id="posts-container">
    {% for post in ordered_posts %}
      {% assign c = site.data.categories | where: "key", post.category | first %}
      {% capture haystack %}{{ post.title }} {{ post.category }} {{ post.tags | join: ' ' }} {{ post.excerpt | strip_html }}{% endcapture %}
      <a href="{{ post.url | relative_url }}" class="post-item"
         data-category="{{ post.category }}"
         data-search="{{ haystack | strip_newlines | downcase | escape_once }}">
        <span class="post-date">{{ post.date | date: "%y.%m.%d" }}</span>
        <span class="post-title">{{ post.title }}</span>
        <span class="post-tag tag-{{ c.color | default: 'teal' }}">{{ post.category }}</span>
      </a>
    {% endfor %}

    {% if site.posts.size == 0 %}
      <div class="empty-note">// 아직 작성된 글이 없습니다.</div>
    {% endif %}
  </div>

  <div class="empty-note" id="no-match" hidden>// 검색 결과가 없습니다.</div>

</section>

<script>
(function () {
  const items = [...document.querySelectorAll('#posts-container .post-item')];
  const input = document.getElementById('q');
  const clear = document.getElementById('q-clear');
  const count = document.getElementById('result-count');
  let category = 'all';

  function apply() {
    const terms = input.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
    let shown = 0;

    for (const item of items) {
      const hay = item.dataset.search;
      const match = (category === 'all' || item.dataset.category === category)
                 && terms.every(t => hay.includes(t));
      item.hidden = !match;
      if (match) shown++;
    }

    count.textContent = shown;
    document.getElementById('no-match').hidden = shown > 0;
    clear.hidden = input.value === '';
  }

  input.addEventListener('input', apply);
  clear.addEventListener('click', () => { input.value = ''; input.focus(); apply(); });

  document.querySelector('.filter-bar').addEventListener('click', e => {
    const btn = e.target.closest('.filter-btn');
    if (!btn) return;
    category = btn.dataset.filter;
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.toggle('active', b === btn));
    apply();
  });

  // 사이드바 검색창에서 넘어온 ?q=
  const q = new URLSearchParams(location.search).get('q');
  if (q) { input.value = q; }
  apply();
})();
</script>

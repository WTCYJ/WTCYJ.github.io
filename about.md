---
layout: default
title: About
permalink: /about/
---

{% assign p = site.data.profile %}

<div class="about-layout">

  <div class="about-head">
    <img class="about-avatar" src="{{ '/assets/img/monkey-patch/pout-monkey.png' | relative_url }}" alt="입을 내민 원숭이">
    <div>
      <h1 class="about-name">{{ p.name }}{% if p.real_name %} <span class="about-realname">{{ p.real_name }}</span>{% endif %}</h1>
      <div class="about-role">{{ p.role }}</div>
      {% if p.affiliations.size > 0 %}
        <div class="profile-affil">
          {% for a in p.affiliations %}<span>{{ a }}</span>{% endfor %}
        </div>
      {% endif %}
    </div>
  </div>

  {% if p.tags.size > 0 %}
    <div class="hash-list" style="margin-bottom:1.5rem;">
      {% for t in p.tags %}<span class="hash-tag">#{{ t }}</span>{% endfor %}
    </div>
  {% endif %}

  <p class="about-bio">{{ p.bio }}</p>

  {% if p.now.size > 0 %}
  <div class="section-header">
    <span class="section-label">now — 하고 있는 것</span>
    <div class="section-line"></div>
  </div>

  <div class="now-list">
    {% for n in p.now %}
      <div class="now-item">
        <span class="now-dot"></span>
        <div>
          <div class="now-text">{{ n.text }}</div>
          {% if n.note and n.note != '' %}<div class="now-note">{{ n.note }}</div>{% endif %}
        </div>
      </div>
    {% endfor %}
  </div>
  {% endif %}

  {% if p.timeline.size > 0 %}
  <div class="section-header" style="margin-top:2.5rem;">
    <span class="section-label">timeline — 이력</span>
    <div class="section-line"></div>
  </div>

  <div class="timeline">
    {% for t in p.timeline %}
      <div class="tl-item">
        <div class="tl-period">{{ t.period }}</div>
        <div class="tl-title">{{ t.title }}</div>
        {% if t.org and t.org != '' %}<div class="tl-org">{{ t.org }}</div>{% endif %}
        {% if t.desc and t.desc != '' %}<div class="tl-desc">{{ t.desc }}</div>{% endif %}
      </div>
    {% endfor %}
  </div>
  {% endif %}

  {% if p.skills.size > 0 %}
  <div class="section-header" style="margin-top:2rem;">
    <span class="section-label">skills</span>
    <div class="section-line"></div>
  </div>

  {% for g in p.skills %}
    <div class="skill-group">
      <div class="skill-group-name">// {{ g.group }}</div>
      <div class="skill-list" style="margin-bottom:0;">
        {% for s in g.items %}<span class="skill-tag">{{ s }}</span>{% endfor %}
      </div>
    </div>
  {% endfor %}
  {% endif %}

  <div class="section-header" style="margin-top:2.5rem;">
    <span class="section-label">categories — 무엇을 쓰는가</span>
    <div class="section-line"></div>
  </div>

  <div class="categories-grid">
    {% for c in site.data.categories %}
      <a href="/category/{{ c.slug }}/" class="cat-card" data-color="{{ c.color }}">
        <span class="cat-icon">{{ c.icon }}</span>
        <div class="cat-name">{{ c.name }}</div>
        <div class="cat-count">{{ site.posts | where: "category", c.key | size }} posts</div>
      </a>
    {% endfor %}
  </div>

  <div class="section-header">
    <span class="section-label">contact</span>
    <div class="section-line"></div>
  </div>

  <div class="link-list">
    {% for l in p.links %}
      <a href="{{ l.url }}" class="btn-neon"{% if l.url contains '://' %} target="_blank" rel="noopener"{% endif %}>{{ l.name }} ↗</a>
    {% endfor %}
  </div>

</div>

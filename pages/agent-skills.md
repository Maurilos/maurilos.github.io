---
layout: page
title: Agent Skills Hub
permalink: /agent-skills/
---

# Agent Skills Hub 精选

<p>
最近同步：{{ site.data.agentskills.meta.updated_at_utc }}
</p>

{% assign summary = site.data.agentskills.summary %}
{% assign curated = site.data.agentskills.curated %}

## 站点概览

{% if summary %}
<ul>
  <li>工具规模：{{ summary.tools_count }}</li>
  <li>项目规模：{{ summary.projects_count }}</li>
  <li>场景数量：{{ summary.scenarios_count }}</li>
  <li>同步频率：每 {{ summary.refresh_hours }} 小时</li>
</ul>
{% else %}
<p>暂无站点概览数据。</p>
{% endif %}

## 热门场景

{% if curated and curated.size > 0 %}
<ul>
  {% for item in curated %}
    <li>
      <a href="{{ item.local_url | relative_url }}" target="_blank" rel="noopener">{{ item.title }}</a>
    </li>
  {% endfor %}
</ul>
{% else %}
<p>暂无场景数据。</p>
{% endif %}

## 精选榜单

{% if curated and curated.size > 0 %}
  {% for block in curated %}
### <a href="{{ block.local_url | relative_url }}" target="_blank" rel="noopener">{{ block.title }}</a>

{% if block.quick_pick and block.quick_pick.name %}
<p>
  <strong>Quick Pick：</strong>
  {% if block.quick_pick.github_url %}
    <a href="{{ block.quick_pick.github_url }}" target="_blank" rel="noopener">{{ block.quick_pick.name }}</a>
  {% else %}
    {{ block.quick_pick.name }}
  {% endif %}
  {% if block.quick_pick.stars %} · ★ {{ block.quick_pick.stars }}{% endif %}
  {% if block.quick_pick.tagline %} · {{ block.quick_pick.tagline }}{% endif %}
</p>
{% endif %}

{% if block.tools and block.tools.size > 0 %}
<ol>
  {% for tool in block.tools limit: 10 %}
    <li>
      <strong>
        {% if tool.github_url %}
          <a href="{{ tool.github_url }}" target="_blank" rel="noopener">{{ tool.name }}</a>
        {% else %}
          {{ tool.name }}
        {% endif %}
      </strong>
      {% if tool.author %} by {{ tool.author }}{% endif %}
      {% if tool.stars %} · ★ {{ tool.stars }}{% endif %}
      {% if tool.meta %} · {{ tool.meta }}{% endif %}
      {% if tool.description %}
        <br>{{ tool.description }}
      {% endif %}
    </li>
  {% endfor %}
</ol>
{% else %}
<p>暂无工具数据。</p>
{% endif %}

<p>
  <small>
    站内页：<a href="{{ block.local_url | relative_url }}" target="_blank" rel="noopener">{{ block.local_url }}</a>
  </small>
</p>

  {% endfor %}
{% else %}
<p>暂无精选榜单数据。</p>
{% endif %}

---
layout: page
title: Agent Skills Hub
permalink: /agent-skills/
---

# Agent Skills Hub 精选

<p>
数据来源：
<a href="https://agentskillshub.top/" target="_blank" rel="noopener">AgentSkillsHub</a><br>
最近同步：{{ site.data.agentskills.meta.updated_at_utc }}
</p>

{% assign summary = site.data.agentskills.summary %}
{% assign scenarios = site.data.agentskills.scenarios %}
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

{% if scenarios and scenarios.size > 0 %}
<ul>
  {% for item in scenarios limit: 24 %}
    <li>
      <a href="{{ item.url }}" target="_blank" rel="noopener">{{ item.name }}</a>
    </li>
  {% endfor %}
</ul>
{% else %}
<p>暂无场景数据。</p>
{% endif %}

## 精选榜单

{% if curated and curated.size > 0 %}
  {% for block in curated %}
    <h3>
      <a href="{{ block.url }}" target="_blank" rel="noopener">{{ block.title }}</a>
    </h3>

    {% if block.quick_pick and block.quick_pick.name %}
      <p>
        <strong>Quick Pick：</strong>{{ block.quick_pick.name }}
        {% if block.quick_pick.stars %} · ★ {{ block.quick_pick.stars }}{% endif %}
        {% if block.quick_pick.tagline %} · {{ block.quick_pick.tagline }}{% endif %}
      </p>
    {% endif %}

    {% if block.tools and block.tools.size > 0 %}
      <ol>
        {% for tool in block.tools limit: 10 %}
          <li>
            <strong>{{ tool.name }}</strong>
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
      <p>这个场景暂时没有抓到条目。</p>
    {% endif %}
  {% endfor %}
{% else %}
<p>暂无精选榜单数据。</p>
{% endif %}

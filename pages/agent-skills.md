---
layout: page
title: Agent Skills Hub
permalink: /agent-skills/
---

# Agent Skills Hub 精选

<p>
数据来源：<a href="https://agentskillshub.top/" target="_blank" rel="noopener">AgentSkillsHub</a><br>
最近同步：{{ site.data.agentskills.meta.updated_at_utc }}
</p>

## 站点统计

<pre>{{ site.data.agentskills.stats | jsonify }}</pre>

## 热门 Trending

<pre>{{ site.data.agentskills.trending | jsonify }}</pre>

## 高分 Top Rated

<pre>{{ site.data.agentskills.top-rated | jsonify }}</pre>

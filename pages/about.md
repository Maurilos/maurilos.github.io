---
layout: page
title: 关于 Maurilos
description: 一个关于技术实践、网络探索、工具分享、生活观察与个人思考的博客。
keywords: Maurilos, Maurilos, 个人博客, 技术博客, 网络探索, 实用工具, 数字生活, 编程学习, 网站搭建, 生活思考
comments: false
menu: 关于
permalink: /about/
---

关于 Maurilos

你好，我是 Maurilos

一个对网络世界充满好奇的人，也是在数字时代里慢慢学习、摸索和建立自己系统的普通人。

我喜欢研究代码、网站、工具和各种有意思的技术。对我来说，编程不只是解决问题的方法，也是一种理解世界的方式。每一次折腾、每一次报错、每一次成功运行，都是和这个数字世界的一次对话。

我不迷信年龄，也不害怕起步晚。只要还愿意学习，还愿意探索，就永远有重新开始的可能。

这个博客会记录我的技术实践、网络观察、生活感悟和一些零散但真实的思考。

Maurilos，不只是一个名字，也是一种持续探索的态度。



## 联系

<ul>
{% for website in site.data.social %}
<li>{{website.sitename }}：<a href="{{ website.url }}" target="_blank">@{{ website.name }}</a></li>
{% endfor %}
{% if site.url contains 'mazhuang.org' %}
<li>
微信公众号：<br />
<img style="height:192px;width:192px;border:1px solid lightgrey;" src="{{ site.url }}/assets/images/qrcode.jpg" alt="闷骚的程序员" />
</li>
{% endif %}
</ul>


## Skill Keywords

{% for skill in site.data.skills %}
### {{ skill.name }}
<div class="btn-inline">
{% for keyword in skill.keywords %}
<button class="btn btn-outline" type="button">{{ keyword }}</button>
{% endfor %}
</div>
{% endfor %}

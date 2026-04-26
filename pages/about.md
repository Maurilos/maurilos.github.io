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

你好，我是 Maurilos。

我是一个对网络世界始终保持好奇的人，也是在数字时代中不断学习、尝试，并慢慢搭建自己知识体系的普通探索者。

我喜欢研究代码、网站、工具，以及各种有趣的技术。对我来说，编程不只是解决问题的手段，更像是一种理解世界的方式。每一次调试、每一个报错、每一次成功运行，都是我与数字世界之间的一次交流。

我不迷信年龄，也不害怕起步晚。只要还愿意学习、还愿意探索，人生就始终有重新开始的可能。

这个博客会记录我的技术实践、网络观察、生活感悟，以及那些零散却真实的思考。

Maurilos，不只是一个名字，更是一种持续探索、不断前行的态度。

我的邮箱,如有问题可以和我联系. MLS.lab@hotmail.com



## 联系

<ul>
{% for website in site.data.social %}
<li>{{website.sitename }}：<a href="{{ website.url }}" target="_blank">@{{ website.name }}</a></li>
{% endfor %}
{% if site.url contains 'MLS.lab@hotmail.com' %}
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

'use strict';
(() => {
  const $ = selector => document.querySelector(selector);
  const list = $('#city-list');
  const mapElement = $('#map');
  const normalize = text => text.toLocaleLowerCase('ru').replaceAll('ё', 'е').trim();
  const formatDate = text => new Date(text + 'T12:00:00Z').toLocaleDateString('ru-RU', {timeZone: 'UTC', day: 'numeric', month: 'long', year: 'numeric'});
  let cities = [], active, atlas;

  function selectCity(id, {updateURL = true, reveal = true, focusMap = false} = {}) {
    active = cities.find(city => city.id === id) || cities.find(city => city.id === 'moscow');
    $('#city-title').textContent = active.name;
    $('#today').textContent = formatDate(active.today);
    const offset = new Intl.DateTimeFormat('ru-RU', {timeZone: active.timezone, timeZoneName: 'shortOffset'}).formatToParts(new Date(active.today + 'T12:00:00Z')).find(part => part.type === 'timeZoneName').value.replace('GMT', 'UTC');
    $('#timezone').textContent = `Местное время города · ${offset}`;
    $('#timezone').title = active.timezone;
    $('#rise').textContent = active.times.sunrise || 'Нет восхода';
    $('#set').textContent = active.times.sunset || 'Нет заката';
    $('#rise').classList.toggle('no-event', !active.times.sunrise);
    $('#set').classList.toggle('no-event', !active.times.sunset);
    const last = new Date(active.until_exclusive + 'T12:00:00Z');
    last.setUTCDate(last.getUTCDate() - 1);
    $('#period').textContent = `С ${formatDate(active.from)} по ${formatDate(last.toISOString().slice(0, 10))} · ${active.events} событий по 10 минут.`;
    $('#polar').hidden = active.latitude < 65;
    const url = `https://brodov.net/sun-calendar/${active.id}.ics`;
    $('#calendar-url').value = url;
    $('#subscribe').href = url.replace('https:', 'webcal:');
    $('#download').href = active.id + '.ics';
    $('#copy-status').textContent = '';
    list.querySelectorAll('[data-city]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.city === active.id)));
    $('#map-selection').textContent = 'Выбран город: ' + active.name;
    if (updateURL) history.replaceState(null, '', '#' + active.id);
    if (atlas) atlas.selectionChanged(reveal, focusMap);
  }

  function makeButton(text, callback, className = '') {
    const button = document.createElement('button');
    button.type = 'button'; button.textContent = text; button.className = className;
    button.addEventListener('click', callback);
    return button;
  }

  class Atlas {
    constructor(svg, metadata) {
      this.svg = svg; this.meta = metadata; this.view = 'all';
      this.camera = metadata.bounds.all.slice();
      this.byId = new Map(cities.map(city => [city.id, city]));
      if (cities.some(city => !metadata.points[city.id])) throw new Error('Incomplete map');
      this.terrain = svg.querySelector('[data-terrain]');
      if (!this.terrain) throw new Error('Missing geography');
      svg.setAttribute('aria-hidden', 'true');
      this.overlay = this.node('g', {'data-overlay': 'true'}); svg.append(this.overlay);
      svg.addEventListener('click', event => {
        const point = event.target.closest('[data-point]');
        if (point) this.targets.querySelector(`[data-members~="${point.dataset.point}"]`)?.click();
      });
      this.targets = document.createElement('div'); this.targets.className = 'map-targets';
      this.tools = document.createElement('div'); this.tools.className = 'map-tools';
      for (const [label, title, action] of [ ['+', 'Приблизить карту', () => this.zoom(1.8)], ['−', 'Отдалить карту', () => this.zoom(1 / 1.8)], ['↺', 'Сбросить масштаб области', () => this.region(this.view)] ]) {
        const button = makeButton(label, action); button.setAttribute('aria-label', title); button.title = title; this.tools.append(button);
      }
      mapElement.replaceChildren(svg, this.targets);
      document.querySelector('.map-heading').append(this.tools);
      document.querySelectorAll('[data-view]').forEach(button => {
        button.disabled = false;
        button.addEventListener('click', () => this.region(button.dataset.view));
      });
      $('#map-chosen').hidden = false;
      $('#locate-city').addEventListener('click', () => this.locate());
      mapElement.addEventListener('keydown', event => { if (event.key === 'Escape' && this.popup) { event.preventDefault(); this.closePopup(true); } });
      this.resizeObserver = new ResizeObserver(() => { this.closePopup(); this.render(); });
      this.resizeObserver.observe(mapElement);
      document.fonts.ready.then(() => this.render());
      this.render();
    }
    node(name, attrs = {}) {
      const node = document.createElementNS('http://www.w3.org/2000/svg', name);
      for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
      return node;
    }
    region(key) {
      this.view = key; this.camera = this.meta.bounds[key].slice(); this.closePopup();
      document.querySelectorAll('[data-view]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.view === key)));
      this.render();
    }
    fit() {
      const width = mapElement.clientWidth, height = mapElement.clientHeight;
      const [x0, y0, x1, y1] = this.camera;
      const padX = width < 500 ? 34 : 52, padY = 54;
      const scale = Math.min((width - padX * 2) / Math.max(1, x1 - x0), (height - padY * 2) / Math.max(1, y1 - y0));
      return {width, height, scale, tx: width / 2 - (x0 + x1) / 2 * scale, ty: height / 2 - (y0 + y1) / 2 * scale};
    }
    screen(id, frame = this.fit()) {
      const [x, y] = this.meta.points[id];
      return {x: x * frame.scale + frame.tx, y: y * frame.scale + frame.ty};
    }
    onScreen(id, margin = 26) {
      const frame = this.fit(), point = this.screen(id, frame);
      return point.x >= margin && point.y >= margin && point.x <= frame.width - margin && point.y <= frame.height - margin;
    }
    locate() {
      const region = Object.keys(this.meta.regions).find(key => key !== 'all' && this.meta.regions[key].includes(active.id)) || 'all';
      this.region(region);
      if (!this.onScreen(active.id)) this.region('all');
      this.focusSelected();
    }
    selectionChanged(reveal, focus) {
      this.closePopup();
      if (reveal && !this.onScreen(active.id)) {
        const region = Object.keys(this.meta.regions).find(key => key !== 'all' && this.meta.regions[key].includes(active.id)) || 'all';
        this.region(region);
      } else this.render();
      if (focus) this.focusSelected();
    }
    focusSelected() {
      this.targets.querySelector(`[data-members~="${active.id}"]`)?.focus({preventScroll: true});
    }
    zoom(factor) {
      const [x0, y0, x1, y1] = this.camera;
      const center = this.onScreen(active.id) ? this.meta.points[active.id] : [(x0 + x1) / 2, (y0 + y1) / 2];
      let width = (x1 - x0) / factor, height = (y1 - y0) / factor;
      const fullWidth = this.meta.bounds.all[2] - this.meta.bounds.all[0];
      if (width < fullWidth / 300) return;
      if (width > fullWidth * 1.8) { this.region('all'); return; }
      this.camera = [center[0] - width / 2, center[1] - height / 2, center[0] + width / 2, center[1] + height / 2];
      this.closePopup(); this.render();
    }
    closePopup(restore = false) {
      if (!this.popup) return;
      this.popup.remove(); this.popup = null;
      if (restore) { if (this.opener?.isConnected) this.opener.focus({preventScroll: true}); else this.focusSelected(); }
    }
    popupFor(group, opener, x, y) {
      this.closePopup(); this.opener = opener;
      const panel = document.createElement('div'); panel.className = 'map-popup'; panel.setAttribute('role', 'dialog'); panel.setAttribute('aria-label', 'Города рядом');
      const heading = document.createElement('div'); heading.className = 'popup-heading';
      const title = document.createElement('h3'); title.textContent = 'Города рядом'; heading.append(title);
      const close = makeButton('×', () => this.closePopup(true), 'popup-close'); close.setAttribute('aria-label', 'Закрыть список городов'); heading.append(close); panel.append(heading);
      const choices = document.createElement('div'); choices.className = 'popup-cities';
      for (const point of group.slice().sort((a, b) => a.city.name.localeCompare(b.city.name, 'ru'))) {
        const button = makeButton(point.city.name, () => selectCity(point.city.id, {reveal: false, focusMap: true}));
        button.dataset.city = point.city.id; button.setAttribute('aria-pressed', String(point.city.id === active.id)); choices.append(button);
      }
      panel.append(choices);
      panel.append(makeButton('Приблизить эти города', () => {
        const coords = group.map(point => this.meta.points[point.city.id]);
        this.camera = [Math.min(...coords.map(p => p[0])), Math.min(...coords.map(p => p[1])), Math.max(...coords.map(p => p[0])), Math.max(...coords.map(p => p[1]))];
        this.closePopup(); this.render(); this.targets.querySelector('button')?.focus({preventScroll: true});
      }, 'popup-zoom'));
      this.popup = panel; mapElement.append(panel);
      panel.style.left = Math.max(10, Math.min(mapElement.clientWidth - panel.offsetWidth - 10, x + 12)) + 'px';
      panel.style.top = Math.max(10, Math.min(mapElement.clientHeight - panel.offsetHeight - 10, y + 12)) + 'px';
      close.focus({preventScroll: true});
    }
    groups(points) {
      // Merge overlapping 44px targets by their centroids. Unlike connected
      // components of city points, this cannot chain an entire continent.
      const groups = points.map(point => [point]);
      const center = group => ({x: group.reduce((sum, p) => sum + p.x, 0) / group.length, y: group.reduce((sum, p) => sum + p.y, 0) / group.length});
      while (true) {
        let nearest = null, distance = Infinity;
        for (let a = 0; a < groups.length; a++) for (let b = a + 1; b < groups.length; b++) {
          const p = center(groups[a]), q = center(groups[b]);
          const dx = Math.abs(p.x - q.x), dy = Math.abs(p.y - q.y);
          if (dx < 48 && dy < 48 && dx * dx + dy * dy < distance) {
            nearest = [a, b]; distance = dx * dx + dy * dy;
          }
        }
        if (!nearest) break;
        const [a, b] = nearest; groups[a].push(...groups[b]); groups.splice(b, 1);
      }
      return groups;
    }

    render() {
      const focusId = this.targets.contains(document.activeElement) ? document.activeElement.dataset.members?.split(' ')[0] : null;
      const frame = this.fit(), {width, height, scale, tx, ty} = frame;
      if (!width) return;
      this.svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
      this.terrain.setAttribute('transform', `translate(${tx} ${ty}) scale(${scale})`);
      this.overlay.replaceChildren(); this.targets.replaceChildren();
      const points = cities.map(city => ({city, ...this.screen(city.id, frame)})).filter(point => point.x >= 24 && point.y >= 24 && point.x <= width - 24 && point.y <= height - 24);
      const selected = points.find(point => point.city.id === active.id);
      if (selected) this.overlay.append(this.node('circle', {cx: selected.x, cy: selected.y, r: 11, class: 'map-halo'}));
      for (const point of points) this.overlay.append(this.node('circle', {cx: point.x, cy: point.y, r: point.city.id === active.id ? 5 : 3.5, class: 'map-dot' + (point.city.id === active.id ? ' selected' : ''), 'data-point': point.city.id}));
      const groups = this.groups(points);
      const reserved = [];
      for (const group of groups) {
        let x = group.reduce((sum, point) => sum + point.x, 0) / group.length;
        let y = group.reduce((sum, point) => sum + point.y, 0) / group.length;
        const containsActive = group.some(point => point.city.id === active.id);
        const button = makeButton('', event => {
          if (group.length === 1) selectCity(group[0].city.id, {reveal: false, focusMap: event.detail === 0});
          else this.popupFor(group, event.currentTarget, x, y);
        }, 'map-target');
        button.dataset.members = group.map(point => point.city.id).join(' ');
        button.style.left = (x - 22) + 'px'; button.style.top = (y - 22) + 'px';
        button.setAttribute('aria-pressed', String(containsActive));
        if (group.length === 1) {
          button.dataset.city = group[0].city.id; button.setAttribute('aria-label', group[0].city.name); button.title = group[0].city.name;
        } else {
          const badge = document.createElement('span'); badge.className = 'cluster-count'; badge.textContent = group.length; button.append(badge);
          button.setAttribute('aria-label', `${group.length} городов рядом: ${group.slice(0, 3).map(point => point.city.name).join(', ')}. Открыть список`);
          button.setAttribute('aria-haspopup', 'dialog');
          reserved.push({x: x - 16, y: y - 16, width: 32, height: 32});
        }
        this.targets.append(button);
      }
      this.labels(points, reserved, frame);
      if (focusId) this.targets.querySelector(`[data-members~="${focusId}"]`)?.focus({preventScroll: true});
    }
    labels(points, reserved, frame) {
      const majors = ['moscow', 'saint-petersburg', 'kaliningrad', 'minsk', 'samara', 'murmansk', 'yekaterinburg', 'novosibirsk', 'krasnoyarsk', 'irkutsk', 'yakutsk', 'vladivostok', 'magadan', 'petropavlovsk-kamchatsky', 'anadyr'];
      const canvas = document.createElement('canvas'), context = canvas.getContext('2d');
      const ranked = points.slice().sort((a, b) => {
        const score = point => point.city.id === active.id ? -100 : majors.includes(point.city.id) ? majors.indexOf(point.city.id) : 100;
        return score(a) - score(b);
      });
      let displayed = 0;
      const overlap = (a, b) => a.x < b.x + b.width + 5 && a.x + a.width + 5 > b.x && a.y < b.y + b.height + 4 && a.y + a.height + 4 > b.y;
      for (const point of ranked) {
        const selected = point.city.id === active.id;
        if (!selected && (displayed >= (this.view === 'all' ? 12 : 22) || (this.view === 'all' && !majors.includes(point.city.id)))) continue;
        const size = selected ? 16 : 14; context.font = `${size}px "PT Sans"`;
        const width = context.measureText(point.city.name).width + 4, height = size + 5;
        const candidates = [[point.x + 11, point.y - height - 5], [point.x - width - 11, point.y - height - 5], [point.x - width / 2, point.y + 13], [point.x - width / 2, point.y - height - 18], [8, frame.height - height - 12]];
        let box;
        for (const [x, y] of candidates.slice(0, selected ? 5 : 4)) {
          const next = {x: Math.max(8, Math.min(frame.width - width - 8, x)), y: Math.max(8, Math.min(frame.height - height - 8, y)), width, height};
          if (!reserved.some(rect => overlap(next, rect))) { box = next; break; }
        }
        if (!box && !selected) continue;
        if (!box) box = {x: 8, y: frame.height - height - 10, width, height};
        if (selected) this.overlay.append(this.node('line', {x1: point.x, y1: point.y, x2: Math.max(box.x, Math.min(box.x + box.width, point.x)), y2: Math.max(box.y, Math.min(box.y + box.height, point.y)), class: 'label-leader'}));
        const label = this.node('text', {x: box.x + 2, y: box.y + size, class: 'map-label' + (selected ? ' selected' : ''), 'data-label-for': point.city.id});
        label.textContent = point.city.name; this.overlay.append(label); reserved.push(box); displayed++;
      }
    }
  }

  async function loadMap() {
    try {
      const [svgResponse, metadataResponse] = await Promise.all([fetch('map.svg'), fetch('map-projection.json')]);
      if (!svgResponse.ok || !metadataResponse.ok) throw new Error('Map unavailable');
      const [text, metadata] = await Promise.all([svgResponse.text(), metadataResponse.json()]);
      const svg = new DOMParser().parseFromString(text, 'image/svg+xml').documentElement;
      if (svg.tagName !== 'svg') throw new Error('Invalid map');
      atlas = new Atlas(document.importNode(svg, true), metadata);
    } catch {
      const message = document.createElement('p'); message.className = 'map-message';
      message.textContent = 'Карта временно недоступна. Выберите город в списке ниже.';
      mapElement.replaceChildren(message);
      document.querySelectorAll('[data-view]').forEach(button => button.disabled = true);
      $('#map-chosen').hidden = true;
    }
  }

  async function init() {
    try {
      const response = await fetch('cities.json');
      if (!response.ok) throw new Error('Cities unavailable');
      const data = await response.json();
      if (!Array.isArray(data.cities) || !data.cities.some(city => city.id === 'moscow')) throw new Error('Invalid cities');
      cities = data.cities;
      for (const city of cities) {
        const button = makeButton(city.name, () => selectCity(city.id));
        button.dataset.city = city.id; button.dataset.search = normalize([city.name, city.region || '', city.search_terms || ''].join(' ')); list.append(button);
      }
      selectCity(location.hash.slice(1), {updateURL: false});
      window.addEventListener('hashchange', () => selectCity(location.hash.slice(1), {updateURL: false}));
      $('#search').disabled = false;
      $('#search').addEventListener('input', event => {
        const query = normalize(event.target.value); let count = 0;
        list.querySelectorAll('button').forEach(button => { button.hidden = !button.dataset.search.includes(query); if (!button.hidden) count++; });
        $('#count').textContent = `Городов: ${count}`; $('#empty').hidden = count !== 0;
      });
      $('#copy').addEventListener('click', async () => {
        const input = $('#calendar-url');
        try { await navigator.clipboard.writeText(input.value); $('#copy-status').textContent = 'Ссылка скопирована'; }
        catch { input.focus(); input.select(); $('#copy-status').textContent = 'Скопируйте выделенную ссылку вручную'; }
      });
      $('.all-links').open = false;
      loadMap();
    } catch {
      $('#count').textContent = 'Не удалось загрузить города. Выберите календарь в списке ниже.';
      $('.selection').hidden = true; $('.all-links').open = true;
      mapElement.replaceChildren(Object.assign(document.createElement('p'), {className: 'map-message', textContent: 'Календари доступны в списке «Все города» ниже.'}));
    }
  }
  init();
})();

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const themeSource = fs.readFileSync(
  path.join(__dirname, '../src/llm_batch/monitor/static/theme.js'),
  'utf8',
);
const themeKey = 'lndc_theme';

function eventSurface() {
  const listeners = new Map();
  return {
    addEventListener(type, listener) {
      if (!listeners.has(type)) listeners.set(type, []);
      listeners.get(type).push(listener);
    },
    dispatch(type, event = {}) {
      for (const listener of listeners.get(type) || []) listener(event);
    },
  };
}

// 실제 브라우저처럼 head 스크립트 실행 시에는 테마 버튼이 아직 없다.
function openDashboard({ dark = false, store = new Map(), failRead = false, failWrite = false } = {}) {
  let ready = false;
  const buttons = ['light', 'dark'].map(choice => ({
    ...eventSurface(),
    dataset: { themeChoice: choice },
    attributes: {},
    setAttribute(name, value) { this.attributes[name] = value; },
  }));
  const media = { ...eventSurface(), matches: dark };
  const window = { ...eventSurface(), matchMedia: () => media };
  const document = {
    ...eventSurface(),
    documentElement: { dataset: {}, style: {} },
    querySelectorAll: () => ready ? buttons : [],
  };
  const localStorage = {
    getItem(key) {
      if (failRead) throw new Error('브라우저가 저장소 읽기를 차단함');
      return store.get(key) ?? null;
    },
    setItem(key, value) {
      if (failWrite) throw new Error('브라우저가 저장소 쓰기를 차단함');
      store.set(key, value);
    },
  };
  vm.runInNewContext(themeSource, { window, document, localStorage }, { filename: 'theme.js' });

  return {
    firstPaint: document.documentElement.dataset.theme,
    showControls() {
      ready = true;
      document.dispatch('DOMContentLoaded');
    },
    choose(theme) {
      assert.ok(ready, '버튼이 표시된 후 선택해야 한다');
      buttons.find(button => button.dataset.themeChoice === theme).dispatch('click');
    },
    changeSystem(dark) {
      media.matches = dark;
      media.dispatch('change', { matches: dark });
    },
    otherTabChanges(key, value) {
      if (key === null) store.clear();
      else if (value === null) store.delete(key);
      else store.set(key, value);
      window.dispatch('storage', { key, newValue: value });
    },
    expectTheme(theme) {
      assert.equal(document.documentElement.dataset.theme, theme);
      assert.equal(document.documentElement.style.colorScheme, theme);
      if (ready) {
        for (const button of buttons) {
          assert.equal(button.attributes['aria-pressed'], String(button.dataset.themeChoice === theme));
        }
      }
    },
  };
}

test('저장된 선택이 없으면 첫 화면과 이후 OS 테마 변경을 따른다', () => {
  for (const dark of [false, true]) {
    const dashboard = openDashboard({ dark });
    assert.equal(dashboard.firstPaint, dark ? 'dark' : 'light');
    dashboard.showControls();
    dashboard.expectTheme(dark ? 'dark' : 'light');
    dashboard.changeSystem(!dark);
    dashboard.expectTheme(dark ? 'light' : 'dark');
  }
});

test('직접 고른 모드는 OS 변경에 유지되며 새로고침 후에도 복원된다', () => {
  const store = new Map();
  const dashboard = openDashboard({ dark: false, store });
  dashboard.showControls();
  dashboard.choose('dark');
  dashboard.expectTheme('dark');
  assert.equal(store.get(themeKey), 'dark');
  dashboard.changeSystem(true);
  dashboard.changeSystem(false);
  dashboard.expectTheme('dark');

  const reloaded = openDashboard({ dark: false, store });
  assert.equal(reloaded.firstPaint, 'dark');
  reloaded.showControls();
  reloaded.expectTheme('dark');
  reloaded.choose('light');
  reloaded.changeSystem(true);
  reloaded.expectTheme('light');
  assert.equal(store.get(themeKey), 'light');
});

test('다른 탭의 선택을 동기화하고 선택 삭제나 저장소 비우기 후 OS 설정으로 돌아간다', () => {
  const dashboard = openDashboard({ dark: true });
  dashboard.showControls();
  dashboard.otherTabChanges(themeKey, 'light');
  dashboard.expectTheme('light');
  dashboard.changeSystem(false);
  dashboard.changeSystem(true);
  dashboard.expectTheme('light');
  dashboard.otherTabChanges('unrelated-preference', 'dark');
  dashboard.expectTheme('light');
  dashboard.otherTabChanges(themeKey, null);
  dashboard.expectTheme('dark');
  dashboard.changeSystem(false);
  dashboard.expectTheme('light');
  dashboard.otherTabChanges(themeKey, 'dark');
  dashboard.expectTheme('dark');
  dashboard.otherTabChanges(null, null);
  dashboard.expectTheme('light');
});

test('저장소 읽기나 쓰기가 차단되어도 현재 화면의 모드 선택은 계속 동작한다', () => {
  for (const [failRead, failWrite] of [[true, false], [false, true], [true, true]]) {
    const store = new Map();
    const dashboard = openDashboard({ dark: true, store, failRead, failWrite });
    assert.equal(dashboard.firstPaint, 'dark');
    dashboard.showControls();
    dashboard.choose('light');
    dashboard.expectTheme('light');
    dashboard.changeSystem(false);
    dashboard.changeSystem(true);
    dashboard.expectTheme('light');
    dashboard.choose('dark');
    dashboard.expectTheme('dark');
    assert.equal(store.get(themeKey), failWrite ? undefined : 'dark');
  }
});

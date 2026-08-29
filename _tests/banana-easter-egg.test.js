const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

class FakeElement {
  constructor() {
    this.listeners = new Map();
    this.textContent = '';
    this.open = false;
    this.attributes = new Map();
    this.classList = {
      add() {},
      remove() {}
    };
  }

  addEventListener(type, listener) {
    this.listeners.set(type, listener);
  }

  dispatch(type, event = { target: this }) {
    this.listeners.get(type)?.(event);
  }

  showModal() {
    this.open = true;
  }

  close() {
    this.open = false;
  }

  focus() {}

  setAttribute(name, value) {
    this.attributes.set(name, value);
    if (name === 'open') this.open = true;
  }

  get offsetWidth() {
    return 156;
  }
}

const selectors = [
  '#banana-trigger',
  '#banana-hint',
  '#banana-progress',
  '#banana-reward',
  '#banana-close',
  '#banana-take',
  '#banana-taken'
];
const elements = Object.fromEntries(selectors.map((selector) => [selector, new FakeElement()]));
const document = {
  querySelector(selector) {
    return elements[selector] ?? null;
  }
};

const scriptPath = path.join(__dirname, '..', 'assets', 'js', 'banana-easter-egg.js');
const source = fs.readFileSync(scriptPath, 'utf8');
vm.runInNewContext(source, { document });

const trigger = elements['#banana-trigger'];
const reward = elements['#banana-reward'];

for (let index = 0; index < 1012; index += 1) trigger.dispatch('click');
assert.equal(reward.open, false, '1012번째까지는 보상 창이 열리면 안 됩니다.');
assert.equal(elements['#banana-progress'].textContent, '바나나를 1012번 눌렀습니다.');

trigger.dispatch('click');
assert.equal(reward.open, true, '1013번째에 보상 창이 열려야 합니다.');
assert.equal(elements['#banana-hint'].textContent, '바나나 금고가 열렸다!');

elements['#banana-close'].dispatch('click');
assert.equal(reward.open, false, '닫기 버튼이 보상 창을 닫아야 합니다.');

trigger.dispatch('click');
assert.equal(reward.open, true, '잠금 해제 후 바나나를 누르면 보상 창이 다시 열려야 합니다.');

elements['#banana-take'].dispatch('click');
assert.equal(elements['#banana-taken'].textContent, '바나나를 챙겼습니다. 잘 보관하세요.');

console.log('banana easter egg: 1012 locked, 1013 unlocked, reward reusable');

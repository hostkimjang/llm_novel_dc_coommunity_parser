const path = require('node:path');

// Tailwind 3.4.17의 기본 팔레트를 CSS RGB 토큰으로 노출합니다.
// dashboard.css에서 같은 변수를 바꾸면 동적 유틸리티도 테마를 따릅니다.
const paletteNames = [
  'slate', 'gray', 'zinc', 'neutral', 'stone', 'red', 'orange', 'amber',
  'yellow', 'lime', 'green', 'emerald', 'teal', 'cyan', 'sky', 'blue',
  'indigo', 'violet', 'purple', 'fuchsia', 'pink', 'rose',
];
const workerColors = ['blue', 'purple', 'pink', 'amber', 'emerald', 'red', 'sky', 'lime', 'slate'];

function tokenizedPalette(name, palette) {
  return Object.fromEntries(Object.entries(palette).map(([shade, hex]) => {
    const channels = hex.slice(1).match(/.{2}/g).map(channel => parseInt(channel, 16)).join(' ');
    return [shade, `rgb(var(--color-${name}-${shade}, ${channels}) / <alpha-value>)`];
  }));
}

module.exports = {
  content: [path.resolve(__dirname, '../../src/llm_batch/monitor/static/index.html')],
  // 실행 중 조합되는 워커 필터 클래스는 정적 스캔에 나타나지 않습니다.
  safelist: workerColors.flatMap(color => [
    `bg-${color}-600`,
    `bg-${color}-900/40`,
    `bg-${color}-900/60`,
    `bg-${color}-900/70`,
    `hover:bg-${color}-900/70`,
    `text-${color}-300`,
    `ring-${color}-400`,
  ]),
  theme: {
    extend: {
      colors: ({ colors }) => Object.fromEntries(
        paletteNames.map(name => [name, tokenizedPalette(name, colors[name])]),
      ),
    },
  },
  plugins: [],
};

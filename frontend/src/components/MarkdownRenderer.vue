<script setup lang="ts">
import { computed } from 'vue'
import { marked, type Tokens } from 'marked'
import hljs from 'highlight.js/lib/core'
import 'highlight.js/styles/github-dark.css'

// 註冊需要的語言
import javascript from 'highlight.js/lib/languages/javascript'
import python from 'highlight.js/lib/languages/python'
import typescript from 'highlight.js/lib/languages/typescript'
import json from 'highlight.js/lib/languages/json'

hljs.registerLanguage('javascript', javascript)
hljs.registerLanguage('python', python)
hljs.registerLanguage('typescript', typescript)
hljs.registerLanguage('json', json)

const props = defineProps<{
  content: string
  lightSurface?: boolean
  plainSurface?: boolean
}>()

// 配置 marked renderer
const renderer = new marked.Renderer()

function escapeHtml(text: string) {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

renderer.code = function({ text, lang }: Tokens.Code) {
  if (lang && hljs.getLanguage(lang)) {
    try {
      const highlighted = hljs.highlight(text, { language: lang }).value
      return `<pre><code class="hljs language-${lang}">${highlighted}</code></pre>`
    } catch (error) {
      console.error('Highlight.js error:', error)
    }
  }

  const safeText = escapeHtml(text)
  const languageClass = lang ? ` language-${lang}` : ''
  return `<pre><code class="hljs${languageClass}">${safeText}</code></pre>`
}

// 配置 marked
marked.setOptions({
  renderer,
  breaks: true, // 支援換行
  gfm: true // 啟用 GitHub Flavored Markdown
})

const html = computed(() => {
  try {
    return marked(props.content || '') as string
  } catch (error) {
    console.error('Marked parsing error:', error)
    return '<p class="text-red-500">Markdown 解析錯誤</p>'
  }
})
</script>

<template>
  <div
    :class="[
      'markdown-content',
      props.plainSurface
        ? 'plain-surface text-gray-900'
        : props.lightSurface
          ? 'light-surface text-gray-900'
          : 'text-gray-900 dark:text-gray-100'
    ]"
    v-html="html"
  ></div>
</template>

<style scoped>
/* 標題樣式 */
.markdown-content :deep(h1) {
  font-size: 1.5rem;
  font-weight: bold;
  margin-bottom: 0.75rem;
  margin-top: 1.5rem;
   color: rgb(69 10 10); /* red-950 */
   border-bottom: 2px solid rgb(127 29 29); /* red-900 */
  padding-bottom: 0.5rem;
}

.dark .markdown-content:not(.light-surface) :deep(h1) {
   color: rgb(254 202 202); /* red-200 */
   border-bottom-color: rgb(248 113 113); /* red-400 */
}

.markdown-content :deep(h2) {
  font-size: 1.25rem;
  font-weight: bold;
  margin-bottom: 0.5rem;
  margin-top: 1.25rem;
   color: rgb(69 10 10); /* red-950 */
}

.dark .markdown-content:not(.light-surface) :deep(h2) {
   color: rgb(254 202 202); /* red-200 */
}

.markdown-content :deep(h3) {
  font-size: 1.125rem;
  font-weight: 600;
  margin-bottom: 0.5rem;
  margin-top: 1rem;
   color: rgb(69 10 10); /* red-950 */
}

.dark .markdown-content:not(.light-surface) :deep(h3) {
   color: rgb(252 165 165); /* red-300 */
}

.markdown-content :deep(h4) {
  font-size: 1rem;
  font-weight: 600;
  margin-bottom: 0.5rem;
  margin-top: 0.75rem;
   color: rgb(69 10 10); /* red-950 */
}

.dark .markdown-content:not(.light-surface) :deep(h4) {
   color: rgb(254 202 202); /* red-200 */
}

/* 段落與清單 */
.markdown-content :deep(p) {
  margin-bottom: 0.75rem;
  line-height: 1.625;
}

.markdown-content :deep(p:last-child) {
  margin-bottom: 0;
}

.markdown-content :deep(ul) {
  list-style-type: disc;
  list-style-position: inside;
  margin-bottom: 0.75rem;
  margin-left: 1rem;
}

.markdown-content :deep(ul:last-child) {
  margin-bottom: 0;
}

.markdown-content :deep(ul > li) {
  margin-bottom: 0.25rem;
}

.markdown-content :deep(li > p) {
  margin-top: 0;
  margin-bottom: 0.25rem;
}

.markdown-content :deep(li:last-child > p) {
  margin-bottom: 0;
}

.markdown-content :deep(ol) {
  list-style-type: decimal;
  list-style-position: inside;
  margin-bottom: 0.75rem;
  margin-left: 1rem;
}

.markdown-content :deep(ol:last-child) {
  margin-bottom: 0;
}

.markdown-content :deep(ol > li) {
  margin-bottom: 0.25rem;
}

.markdown-content :deep(li > ul),
.markdown-content :deep(li > ol) {
  margin-top: 0.25rem;
}

/* 程式碼區塊 */
.markdown-content :deep(pre) {
  background-color: rgb(243 244 246);
  border-radius: 0.5rem;
  padding: 1rem;
  margin-bottom: 0.75rem;
  overflow-x: auto;
}

.markdown-content :deep(pre:last-child) {
  margin-bottom: 0;
}

.dark .markdown-content:not(.light-surface) :deep(pre) {
  background-color: rgb(31 41 55);
}

.markdown-content :deep(code) {
  font-family: ui-monospace, monospace;
  font-size: 0.875rem;
   background-color: rgb(229 231 235);
  padding: 0.125rem 0.375rem;
  border-radius: 0.25rem;
   color: rgb(17 24 39); /* gray-900 */
}

.dark .markdown-content:not(.light-surface) :deep(code) {
  background-color: rgb(55 65 81);
   color: rgb(243 244 246); /* gray-100 */
}

.markdown-content :deep(pre code) {
  background-color: transparent;
  padding: 0;
  color: inherit;
}

/* 引用 */
.markdown-content :deep(blockquote) {
   border-left: 4px solid rgb(194 65 12); /* orange-700 */
  padding-left: 1rem;
   font-style: italic;
   color: rgb(31 41 55); /* gray-800 */
   margin-bottom: 0.75rem;
   background-color: rgb(239 246 255); /* sky-50 */
  padding-top: 0.5rem;
  padding-bottom: 0.5rem;
  border-radius: 0 0.25rem 0.25rem 0;
}

.markdown-content :deep(blockquote:last-child) {
  margin-bottom: 0;
}

.dark .markdown-content:not(.light-surface) :deep(blockquote) {
   border-left-color: rgb(251 146 60); /* orange-400 */
   color: rgb(226 232 240); /* slate-200 */
   background-color: rgba(51 65 85 / 0.35);
}

/* 強調 */
.markdown-content :deep(strong) {
  font-weight: bold;
   color: rgb(154 52 18); /* orange-800 */
}

.dark .markdown-content:not(.light-surface) :deep(strong) {
   color: rgb(253 186 116); /* orange-300 */
}

.markdown-content :deep(em) {
  font-style: italic;
   color: rgb(30 41 59); /* slate-800 */
}

.dark .markdown-content:not(.light-surface) :deep(em) {
   color: rgb(203 213 225); /* slate-300 */
}

/* 連結 */
.markdown-content :deep(a) {
   color: rgb(154 52 18); /* orange-800 */
   text-decoration: underline;
   transition: color 0.2s;
   text-underline-offset: 2px;
}

.markdown-content :deep(a:hover) {
   color: rgb(124 45 18); /* orange-900 */
}

.dark .markdown-content:not(.light-surface) :deep(a) {
   color: rgb(253 186 116); /* orange-300 */
}

.dark .markdown-content:not(.light-surface) :deep(a:hover) {
   color: rgb(254 215 170); /* orange-200 */
}

/* 表格 */
.markdown-content :deep(table) {
  width: 100%;
  margin-bottom: 0.75rem;
  border-collapse: collapse;
}

.markdown-content :deep(table:last-child) {
  margin-bottom: 0;
}

.markdown-content :deep(th) {
  background-color: rgb(229 231 235);
  font-weight: bold;
  padding: 0.5rem;
  border: 1px solid rgb(209 213 219);
  text-align: left;
}

.dark .markdown-content:not(.light-surface) :deep(th) {
  background-color: rgb(55 65 81);
  border-color: rgb(75 85 99);
}

.markdown-content :deep(td) {
  padding: 0.5rem;
  border: 1px solid rgb(209 213 219);
}

.dark .markdown-content:not(.light-surface) :deep(td) {
  border-color: rgb(75 85 99);
}

.markdown-content :deep(tr:nth-child(even)) {
  background-color: rgb(249 250 251);
}

.dark .markdown-content:not(.light-surface) :deep(tr:nth-child(even)) {
  background-color: rgba(31 41 55 / 0.5);
}

/* 水平線 */
.markdown-content :deep(hr) {
  margin-top: 1rem;
  margin-bottom: 1rem;
  border-top: 2px solid rgb(209 213 219);
}

.dark .markdown-content:not(.light-surface) :deep(hr) {
  border-top-color: rgb(75 85 99);
}

/* 中性閱讀模式：給閱讀文章/題幹用，不套彩色語意 */
.markdown-content.plain-surface :deep(h1),
.markdown-content.plain-surface :deep(h2),
.markdown-content.plain-surface :deep(h3),
.markdown-content.plain-surface :deep(h4) {
  color: rgb(17 24 39) !important; /* gray-900 */
  border-bottom-color: rgb(209 213 219) !important; /* gray-300 */
}

.markdown-content.plain-surface :deep(strong) {
  color: rgb(17 24 39) !important; /* gray-900 */
}

.markdown-content.plain-surface :deep(em) {
  color: rgb(31 41 55) !important; /* gray-800 */
}

.markdown-content.plain-surface :deep(a) {
  color: rgb(17 24 39) !important; /* gray-900 */
}

.markdown-content.plain-surface :deep(a:hover) {
  color: rgb(55 65 81) !important; /* gray-700 */
}

.markdown-content.plain-surface :deep(blockquote) {
  border-left-color: rgb(156 163 175) !important; /* gray-400 */
  color: rgb(31 41 55) !important; /* gray-800 */
  background-color: rgb(249 250 251) !important; /* gray-50 */
}

/* 圖片 */
.markdown-content :deep(img) {
  max-width: 100%;
  height: auto;
  border-radius: 0.5rem;
  box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  margin-top: 0.75rem;
  margin-bottom: 0.75rem;
}

/* plain-surface 深色模式：必須放在所有 dark 規則之後，確保同等權重時覆蓋 */
.dark .markdown-content.plain-surface :deep(h1),
.dark .markdown-content.plain-surface :deep(h2),
.dark .markdown-content.plain-surface :deep(h3),
.dark .markdown-content.plain-surface :deep(h4) {
  color: rgb(229 231 235); /* gray-200 */
  border-bottom-color: rgb(75 85 99); /* gray-600 */
}

.dark .markdown-content.plain-surface :deep(strong) {
  color: rgb(229 231 235); /* gray-200 */
}

.dark .markdown-content.plain-surface :deep(em) {
  color: rgb(209 213 225); /* slate-300 */
}

.dark .markdown-content.plain-surface :deep(a),
.dark .markdown-content.plain-surface :deep(a:hover) {
  color: rgb(209 213 219); /* gray-300 */
}

.dark .markdown-content.plain-surface :deep(blockquote) {
  border-left-color: rgb(107 114 128); /* gray-500 */
  color: rgb(209 213 219); /* gray-300 */
  background-color: rgba(55, 65, 81, 0.3);
}
</style>

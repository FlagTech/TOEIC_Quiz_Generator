<script setup lang="ts">
import { computed } from 'vue'
import MarkdownRenderer from '@/components/MarkdownRenderer.vue'
import type {
  ExplanationAudioOptionItem,
  ExplanationChildItem,
  ExplanationItem,
  ExplanationOptionItem,
} from '@/types/explanations'

const props = defineProps<{
  item: ExplanationItem
  disableGenerate?: boolean
}>()

const emit = defineEmits<{
  generate: [questionNumber: number]
}>()

const hasChildren = computed(() => (props.item.children?.length || 0) > 0)
const hasTopLevelExplanation = computed(() => !!props.item.explanation)
const hasChildExplanations = computed(() => props.item.children?.some(child => !!child.explanation) || false)
const hasAnyExplanation = computed(() => hasTopLevelExplanation.value || hasChildExplanations.value)
const showAnswerSummary = computed(() => !hasChildren.value)
const showStandaloneContent = computed(() => {
  return !!(
    props.item.passage ||
    props.item.passages?.length ||
    props.item.questionText ||
    props.item.blankPosition != null ||
    props.item.options?.length
  )
})

const mediaCardClass = computed(() => {
  return 'border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/40'
})

function emitGenerate() {
  emit('generate', props.item.questionNumber)
}

function optionClass(option: ExplanationOptionItem) {
  if (option.isCorrect) {
    return 'border border-emerald-200 dark:border-emerald-800 bg-emerald-50/60 dark:bg-emerald-950/30 text-gray-900 dark:text-gray-100 font-medium'
  }
  if (option.isUserAnswer) {
    return 'border border-rose-200 dark:border-rose-800 bg-rose-50/60 dark:bg-rose-950/30 text-gray-700 dark:text-gray-200'
  }
  return 'border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800/80 text-gray-700 dark:text-gray-300'
}

function audioOptionClass(option: ExplanationAudioOptionItem) {
  if (option.isCorrect) {
    return 'border-emerald-300 dark:border-emerald-700 bg-emerald-50/60 dark:bg-emerald-950/30'
  }
  if (option.isUserAnswer) {
    return 'border-rose-300 dark:border-rose-700 bg-rose-50/60 dark:bg-rose-950/30'
  }
  return 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800/80'
}

function childBorderClass(child: ExplanationChildItem) {
  return child.isCorrect
    ? 'border-emerald-200 dark:border-emerald-800 bg-white dark:bg-gray-800/70'
    : 'border-rose-200 dark:border-rose-800 bg-white dark:bg-gray-800/70'
}

function childBadgeClass(child: ExplanationChildItem) {
  return child.isCorrect
    ? 'border border-emerald-200 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-300'
    : 'border border-rose-200 dark:border-rose-800 bg-rose-50 dark:bg-rose-950/30 text-rose-700 dark:text-rose-300'
}

function topLevelBadgeClass() {
  return props.item.isCorrect
    ? 'border border-emerald-200 dark:border-emerald-800 bg-emerald-50 dark:bg-emerald-950/30 text-emerald-700 dark:text-emerald-300'
    : 'border border-rose-200 dark:border-rose-800 bg-rose-50 dark:bg-rose-950/30 text-rose-700 dark:text-rose-300'
}

function userAnswerClass(isCorrect: boolean) {
  return isCorrect ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
}
</script>

<template>
  <div class="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-6 shadow-sm">
    <div class="flex items-center justify-between mb-4 gap-3">
      <div class="flex items-center gap-3 flex-wrap">
        <span class="text-lg font-bold text-gray-900 dark:text-white">
          {{ item.title }}
        </span>
        <span :class="['px-3 py-1 rounded-full text-sm font-medium', topLevelBadgeClass()]">
          {{ item.isCorrect ? '✅ 正確' : '❌ 錯誤' }}
        </span>
      </div>

      <template v-if="item.canGenerateExplanation">
        <button
          v-if="!hasAnyExplanation"
          @click="emitGenerate"
          :disabled="item.isGenerating || disableGenerate"
          class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg text-sm font-medium transition-all disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {{ item.isGenerating ? '⏳ 生成中...' : '✨ 生成詳解' }}
        </button>
        <button
          v-else
          @click="emitGenerate"
          :disabled="item.isGenerating || disableGenerate"
          class="px-4 py-2 bg-gray-100 dark:bg-gray-700 hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 rounded-lg text-sm font-medium transition-all disabled:opacity-50"
        >
          {{ item.isGenerating ? '⏳ 生成中...' : '🔄 重新生成' }}
        </button>
      </template>
    </div>

    <div v-if="item.media?.imageUrl" class="mb-5 flex justify-center">
      <img :src="item.media.imageUrl" alt="Question Image" class="max-w-full max-h-64 rounded-xl border border-gray-200 dark:border-gray-700 shadow-sm" />
    </div>

    <div v-if="item.media?.audioUrl" :class="['mb-4 p-4 rounded-lg', mediaCardClass]">
      <h5 v-if="item.media.audioLabel" class="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-2">
        {{ item.media.audioLabel }}
      </h5>
      <audio :src="item.media.audioUrl" controls class="w-full mb-1"></audio>
      <details v-if="item.media.audioText || item.media.transcript" class="mt-1 cursor-pointer">
        <summary class="text-xs text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200 select-none">
          逐字稿
        </summary>
        <p class="text-sm text-gray-700 dark:text-gray-300 mt-1 whitespace-pre-wrap leading-relaxed">
          {{ item.media.audioText || item.media.transcript }}
        </p>
      </details>
    </div>

    <div v-if="item.media?.audioOptions?.length" class="mb-4 space-y-2">
      <div
        v-for="option in item.media.audioOptions"
        :key="option.label"
        :class="['p-3 rounded-lg border-2', audioOptionClass(option)]"
      >
        <div class="flex items-center gap-3">
          <span class="font-bold">{{ option.label }}.</span>
          <audio :src="option.url" controls class="flex-1"></audio>
        </div>
        <details v-if="option.text" class="mt-2 ml-6">
          <summary class="text-xs text-gray-500 dark:text-gray-400 cursor-pointer hover:text-gray-700 dark:hover:text-gray-200 select-none">
            逐字稿
          </summary>
          <p class="text-sm text-gray-700 dark:text-gray-300 mt-1">{{ option.text }}</p>
        </details>
      </div>
    </div>

    <div v-if="showStandaloneContent" class="mb-4 space-y-3">
      <div
        v-if="item.passage && !['[同一篇文章]', '[同組文章]'].includes(item.passage)"
        class="border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/40 rounded-lg p-4 text-sm text-gray-800 dark:text-gray-200 leading-relaxed"
      >
        <MarkdownRenderer :content="item.passage" :plain-surface="true" />
      </div>
      <template v-if="item.passages?.length && !['[同一篇文章]', '[同組文章]'].includes(item.passages[0] || '')">
        <div
          v-for="(passage, index) in item.passages"
          :key="index"
          class="border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/40 rounded-lg p-4 text-sm text-gray-800 dark:text-gray-200 leading-relaxed"
        >
          <MarkdownRenderer :content="passage" :plain-surface="true" />
        </div>
      </template>
      <p v-if="item.blankPosition != null" class="font-semibold text-gray-900 dark:text-white">
        {{ item.questionNumber }}. (Blank {{ item.blankPosition }})
      </p>
      <p v-if="item.questionText" class="font-medium text-gray-900 dark:text-white">
        {{ item.questionNumber }}. {{ item.questionText }}
      </p>
      <div v-if="item.options?.length" class="space-y-1">
        <div
          v-for="option in item.options"
          :key="option.label"
          :class="['flex items-start gap-2 px-3 py-2 rounded-lg text-sm', optionClass(option)]"
        >
          <span class="font-bold shrink-0">({{ option.label }})</span>
          <span>{{ option.text }}</span>
        </div>
      </div>
    </div>

    <div v-if="item.children?.length" class="space-y-4 mb-4">
      <div
        v-for="child in item.children"
        :key="child.id"
        :class="['rounded-xl border p-4', childBorderClass(child)]"
      >
        <div class="flex items-center justify-between mb-2">
          <h5 class="font-semibold text-gray-800 dark:text-white text-sm">
            {{ child.index }}. {{ child.questionText }}
          </h5>
          <span :class="['px-2 py-0.5 rounded text-xs font-bold', childBadgeClass(child)]">
            {{ child.isCorrect ? '✅' : '❌' }}
          </span>
        </div>

        <div class="space-y-1 mb-3">
          <div
            v-for="option in child.options"
            :key="option.label"
            :class="['flex items-start gap-2 px-3 py-2 rounded-lg text-sm', optionClass(option)]"
          >
            <span class="font-bold shrink-0">({{ option.label }})</span>
            <span>{{ option.text }}</span>
          </div>
        </div>

        <div class="grid grid-cols-2 gap-3 mb-3">
          <div class="border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/40 rounded-lg p-3 text-sm">
            <div class="text-gray-600 dark:text-gray-400 mb-0.5">你的答案</div>
            <div :class="['font-bold', userAnswerClass(child.isCorrect)]">
              {{ child.userAnswer || '未作答' }}
            </div>
          </div>
          <div class="border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/40 rounded-lg p-3 text-sm">
            <div class="text-gray-600 dark:text-gray-400 mb-0.5">正確答案</div>
            <div class="font-bold text-green-600">{{ child.correctAnswer }}</div>
          </div>
        </div>

        <div v-if="child.explanation" class="rounded-lg border border-sky-100 dark:border-sky-900/60 bg-sky-50/55 dark:bg-sky-950/20 p-4">
          <div class="flex items-start gap-2">
            <div class="text-sm font-semibold text-blue-900 dark:text-blue-200 shrink-0">AI 詳解</div>
            <div class="text-sm flex-1">
              <MarkdownRenderer :content="child.explanation" :light-surface="true" />
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showAnswerSummary" class="grid grid-cols-2 gap-4 mb-4">
      <div class="border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/40 rounded-lg p-3">
        <div class="text-sm text-gray-600 dark:text-gray-400 mb-1">你的答案</div>
        <div :class="['text-lg font-bold', userAnswerClass(item.isCorrect)]">
          {{ item.userAnswer || '未作答' }}
        </div>
      </div>
      <div class="border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/40 rounded-lg p-3">
        <div class="text-sm text-gray-600 dark:text-gray-400 mb-1">正確答案</div>
        <div class="text-lg font-bold text-green-600 dark:text-green-400">
          {{ item.correctAnswer }}
        </div>
      </div>
    </div>

    <div
      v-if="item.staticHint"
      class="mt-4 rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-900/40 p-4 text-sm text-gray-700 dark:text-gray-300"
    >
      {{ item.staticHint }}
    </div>

    <div v-else-if="item.explanation" class="rounded-lg border border-sky-100 dark:border-sky-900/60 bg-sky-50/55 dark:bg-sky-950/20 p-4">
      <div class="flex items-start gap-3">
        <div class="text-sm font-semibold text-blue-900 dark:text-blue-200 shrink-0">AI 詳解</div>
        <div class="flex-1">
          <MarkdownRenderer :content="item.explanation" :light-surface="true" />
        </div>
      </div>
    </div>
  </div>
</template>

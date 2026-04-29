export type ExplanationPartKey =
  | 'part1'
  | 'part2'
  | 'part3'
  | 'part4'
  | 'part5'
  | 'part6'
  | 'part7_single'
  | 'part7_multiple'

export interface ExplanationOptionItem {
  label: string
  text: string
  isCorrect?: boolean
  isUserAnswer?: boolean
}

export interface ExplanationAudioOptionItem {
  label: string
  url: string
  text?: string
  isCorrect?: boolean
  isUserAnswer?: boolean
}

export interface ExplanationChildItem {
  id: string
  index: number
  questionText: string
  userAnswer?: string
  correctAnswer?: string
  isCorrect: boolean
  options: ExplanationOptionItem[]
  explanation?: string
}

export interface ExplanationMediaItem {
  imageUrl?: string
  audioUrl?: string
  audioLabel?: string
  audioText?: string
  audioOptions?: ExplanationAudioOptionItem[]
  transcript?: string
}

export interface ExplanationItem {
  id: string
  questionNumber: number
  partKey: ExplanationPartKey
  title: string
  isCorrect: boolean
  userAnswer?: string
  correctAnswer?: string
  explanation?: string
  staticHint?: string
  canGenerateExplanation: boolean
  isGenerating?: boolean
  passage?: string
  passages?: string[]
  questionText?: string
  blankPosition?: number | null
  options?: ExplanationOptionItem[]
  media?: ExplanationMediaItem
  children?: ExplanationChildItem[]
}

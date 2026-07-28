<template>
  <div class="markdown-content" v-html="rendered"></div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { marked } from 'marked'
import hljs from 'highlight.js'

const props = defineProps<{ content: string }>()

marked.setOptions({
  breaks: true,
  gfm: true,
  highlight(code: string, lang: string) {
    if (lang && hljs.getLanguage(lang)) {
      return hljs.highlight(code, { language: lang }).value
    }
    return hljs.highlightAuto(code).value
  },
})

const rendered = computed(() => {
  if (!props.content) return ''
  try {
    return marked(props.content)
  } catch {
    return props.content
  }
})
</script>

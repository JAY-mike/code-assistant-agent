<template>
  <div class="page">
    <div class="page-header">
      <div>
        <h1 class="page-title">反馈</h1>
        <p class="page-desc text-secondary text-sm">对 Agent 的回答进行评价，帮助我们持续改进</p>
      </div>
    </div>

    <div class="feedback-intro card">
      <div class="intro-flex">
        <div class="intro-icon">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z"/>
          </svg>
        </div>
        <div>
          <p class="intro-text">在每次对话结束后，你可以对 Agent 的回答进行点赞或点踩。这些反馈会被记录下来，用于评估和改进 Agent 的表现。</p>
          <p class="intro-hint text-xs text-muted">温馨提示：返回 <router-link to="/chat">对话页面</router-link> 与 Agent 交互，消息下方会出现评价按钮。</p>
        </div>
      </div>
    </div>

    <div class="stats-grid">
      <div class="card stat-card">
        <div class="stat-value stat-positive">{{ stats.positive }}</div>
        <div class="stat-label">好评</div>
      </div>
      <div class="card stat-card">
        <div class="stat-value stat-negative">{{ stats.negative }}</div>
        <div class="stat-label">差评</div>
      </div>
      <div class="card stat-card">
        <div class="stat-value">{{ stats.total }}</div>
        <div class="stat-label">总评价数</div>
      </div>
      <div class="card stat-card">
        <div class="stat-value stat-rate">{{ stats.satisfactionRate }}%</div>
        <div class="stat-label">满意度</div>
      </div>
    </div>

    <div class="eval-notes card">
      <h3 class="section-title">消融实验说明</h3>
      <ul class="note-list">
        <li><strong>Hit Rate</strong>（命中率）：检索结果中是否包含正确答案。分数越高=检索越准。</li>
        <li><strong>MRR</strong>（平均倒数排名）：正确答案在检索结果中的排序位置。越靠前分数越高。</li>
        <li><strong>满意度</strong>：基于用户反馈（点赞率）计算的 Agent 表现指标。</li>
        <li>详细的消融实验数据在 <a href="#" @click.prevent>RAG 评估报告</a> 中查看。</li>
      </ul>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'

const stats = ref({
  positive: 0,
  negative: 0,
  total: 0,
  satisfactionRate: 0,
})

// In a full implementation, these would come from the API
onMounted(() => {
  // Placeholder — will be connected when feedback API is ready
  stats.value = {
    positive: 0,
    negative: 0,
    total: 0,
    satisfactionRate: 0,
  }
})
</script>

<style scoped>
.page { padding: 24px; max-width: 960px; margin: 0 auto; }
.page-header { margin-bottom: 24px; }
.page-title { font-size: 1.4rem; font-weight: 700; letter-spacing: -0.02em; margin-bottom: 4px; }
.page-desc { margin: 0; }
.page-header a { color: var(--primary-hover); }

.feedback-intro { margin-bottom: 24px; }
.intro-flex { display: flex; gap: 16px; align-items: flex-start; }
.intro-icon {
  width: 56px; height: 56px;
  border-radius: 14px;
  background: var(--accent-subtle);
  color: var(--accent);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.intro-text { font-size: 0.92rem; line-height: 1.6; margin-bottom: 4px; }
.intro-hint { margin-top: 8px; }

.stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 24px; }
.stat-card { text-align: center; padding: 24px 16px; }
.stat-value { font-size: 2rem; font-weight: 700; letter-spacing: -0.03em; }
.stat-positive { color: var(--success); }
.stat-negative { color: var(--error); }
.stat-rate { color: var(--primary-hover); }
.stat-label { font-size: 0.85rem; color: var(--text-muted); margin-top: 4px; }

.eval-notes { padding: 20px; }
.section-title { font-size: 1rem; font-weight: 600; margin-bottom: 12px; }
.note-list { list-style: none; padding: 0; }
.note-list li {
  padding: 6px 0;
  font-size: 0.9rem;
  color: var(--text-secondary);
  line-height: 1.6;
}
.note-list li::before {
  content: '•';
  color: var(--primary);
  margin-right: 8px;
}
</style>

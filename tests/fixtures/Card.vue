<template>
  <div class="card">
    <h2 class="title">{{ title }}</h2>
    <p>{{ body }}</p>
  </div>
</template>
<script>
export default {
  props: ['title', 'body']
}
</script>
<style scoped>
.card { border: 1px solid #ccc; }
.title { font-weight: bold; }
</style>

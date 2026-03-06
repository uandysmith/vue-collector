<template>
  <div class="counter">
    <span>{{ count }}</span>
    <button @click="increment">+</button>
  </div>
</template>
<script>
export default {
  data() {
    return { count: 0 }
  },
  methods: {
    increment() { this.count++ }
  }
}
</script>
<style>
.counter { display: flex; gap: 8px; }
</style>

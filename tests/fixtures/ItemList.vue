<template>
  <ul>
    <li v-for="item in items" :key="item.id">{{ item.name }}</li>
  </ul>
</template>
<script>
const PAGE_SIZE = 10

export default {
  name: 'ItemList',
  data() {
    return { items: [], pageSize: PAGE_SIZE }
  }
}
</script>

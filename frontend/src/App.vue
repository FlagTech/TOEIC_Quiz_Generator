<script setup lang="ts">
import { RouterView } from 'vue-router'
import NavBar from '@/components/NavBar.vue'
</script>

<template>
  <div class="min-h-dvh bg-gradient-to-br from-blue-50 via-indigo-50 to-purple-50 dark:from-gray-900 dark:via-blue-900/20 dark:to-purple-900/20">
    <NavBar />
    <main class="pt-20 md:pt-24 px-4 md:px-6">
      <div class="max-w-7xl mx-auto w-full">
        <RouterView />
      </div>
    </main>
  </div>
</template>

<style scoped>
</style>

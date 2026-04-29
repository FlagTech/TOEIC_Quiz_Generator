// PostCSS config to enable Tailwind and Autoprefixer
// Ensures Tailwind utility classes and @apply/@layer are processed
// Tailwind v4+ uses a separate PostCSS plugin package
// Install in the frontend directory:
//   npm i -D @tailwindcss/postcss
export default {
  plugins: {
    '@tailwindcss/postcss': {},
  },
}

import { sveltekit } from '@sveltejs/kit/vite';
import tailwindcss from '@tailwindcss/vite';
import { defineConfig } from 'vite';
import { erpDevPlugin } from './vite/plugin-erp-dev';

export default defineConfig({
	plugins: [tailwindcss(), sveltekit(), erpDevPlugin()]
});

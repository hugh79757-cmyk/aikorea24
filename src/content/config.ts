import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const blog = defineCollection({
  loader: glob({ pattern: '**/*.md', base: 'src/content/blog' }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    date: z.string(),
    category: z.string().optional(),
    tags: z.array(z.string()).optional(),
    image: z.string().optional(),
    draft: z.boolean().optional(),
  }),
});

const tools = defineCollection({
  loader: glob({ pattern: '**/*.md', base: 'src/content/tools' }),
  schema: z.object({
    name: z.string(),
    description: z.string(),
    category: z.string(),
    price: z.string(),
    koreanSupport: z.boolean(),
    difficulty: z.string(),
    url: z.string(),
    image: z.string().optional(),
    relatedPost: z.string().optional(),
    useCases: z.array(z.string()).optional(),
    tags: z.array(z.string()).optional(),
    featured: z.boolean().optional(),
    order: z.number().optional(),
  }),
});

export const collections = { blog, tools };

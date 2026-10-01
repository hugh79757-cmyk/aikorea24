import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const blog = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/blog' }),
  schema: z.object({
    title: z.string(),
    description: z.string(),
    date: z.coerce.date(),
    category: z.string(),
    tags: z.array(z.string()).default([]),
    image: z.string().optional(),
    draft: z.boolean().default(false),
  }),
});

const tools = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/tools' }),
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
    useCases: z.array(z.string()).default([]),
    tags: z.array(z.string()).default([]),
    featured: z.boolean().default(false),
    order: z.number().default(99),
    tasks: z.array(z.string()).default([]),
    updated: z.string().optional(),
    priceModel: z.enum(['무료', 'Freemium', '유료', '구독', '일회성']).optional(),
    launchDate: z.string().optional(),
  }),
});


const chronicle = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/chronicle' }),
  schema: z.object({
    title: z.string(),
    date: z.string(),
    year: z.number(),
    month: z.number(),
    category: z.string(),
    summary: z.string(),
    tags: z.array(z.string()).default([]),
    order: z.number().default(0),
  }),
});


const glossary = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/glossary' }),
  schema: z.object({
    term: z.string(),
    en: z.string(),
    category: z.string(),
    level: z.number(),
    short: z.string(),
    detail: z.string(),
    example: z.string(),
    related: z.array(z.string()),
    date: z.string(),
  }),
});

export const collections = { blog, tools, chronicle, glossary };

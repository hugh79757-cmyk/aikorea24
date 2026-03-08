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
  }),
});


const keywords = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/keywords' }),
  schema: z.object({
    keyword: z.string(),
    category: z.string(),
    categoryName: z.string(),
    monthlySearch: z.number(),
    blogCount: z.number(),
    saturation: z.number(),
    grade: z.string(),
    summary: z.string(),
    analysis: z.string(),
    writingGuide: z.string(),
    titles: z.array(z.string()).default([]),
    relatedKeywords: z.array(z.object({
      keyword: z.string(),
      monthlySearch: z.number(),
      saturation: z.number(),
      slug: z.string().optional(),
    })).default([]),
    date: z.coerce.date().default(new Date()),
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

export const collections = { blog, tools, keywords, chronicle };

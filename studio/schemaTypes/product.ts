import {defineField, defineType} from 'sanity'

const BRANDS = ['Chrome Hearts', 'Stüssy', 'Hellstar', 'BAPE', 'Other']
const CONDITIONS = [
  {title: 'DS — brand new', value: 'DS'},
  {title: '10/10', value: '10/10'},
  {title: '9/10', value: '9/10'},
  {title: '8/10', value: '8/10'},
  {title: '7/10', value: '7/10'},
  {title: '6/10 or lower', value: '6/10'},
]
const STATUS = [
  {title: 'Available', value: 'available'},
  {title: 'Reserved', value: 'reserved'},
  {title: 'Sold', value: 'sold'},
]

type Doc = {category?: string; brand?: string}
const cm = (name: string, title: string, description: string, show: string[]) =>
  defineField({
    name,
    title,
    description,
    type: 'number',
    hidden: ({document}) => !show.includes((document as Doc | undefined)?.category ?? ''),
    validation: (r) => r.positive().max(200),
  })

export const product = defineType({
  name: 'product',
  title: 'Product',
  type: 'document',
  fields: [
    defineField({
      name: 'status',
      type: 'string',
      description: 'Reserved = someone sent a receipt and you are holding it. Sold = moves it to the Archive.',
      options: {list: STATUS, layout: 'radio', direction: 'horizontal'},
      initialValue: 'available',
      validation: (r) => r.required(),
    }),
    defineField({
      name: 'images',
      title: 'Photos',
      description: 'First photo is the cover. Second photo shows when someone hovers the card. Add close-ups of tags and flaws.',
      type: 'array',
      of: [{type: 'image', options: {hotspot: true}}],
      options: {layout: 'grid'},
      validation: (r) => r.required().min(1),
    }),
    defineField({
      name: 'name',
      type: 'string',
      validation: (r) => r.required(),
    }),
    defineField({
      name: 'brand',
      type: 'string',
      options: {list: BRANDS, layout: 'radio', direction: 'horizontal'},
      initialValue: 'Chrome Hearts',
      validation: (r) => r.required(),
    }),
    defineField({
      name: 'otherBrand',
      title: 'Brand name',
      type: 'string',
      hidden: ({parent}) => parent?.brand !== 'Other',
      validation: (r) =>
        r.custom((v, ctx) =>
          (ctx.parent as {brand?: string})?.brand === 'Other' && !v ? 'Type the brand' : true,
        ),
    }),
    defineField({
      name: 'category',
      type: 'string',
      options: {
        list: [
          {title: 'Shirts', value: 'shirts'},
          {title: 'Shorts', value: 'shorts'},
          {title: 'Hats', value: 'hats'},
        ],
        layout: 'radio',
        direction: 'horizontal',
      },
      validation: (r) => r.required(),
    }),
    defineField({
      name: 'price',
      title: 'Price (₱)',
      type: 'number',
      validation: (r) => r.required().positive(),
    }),
    defineField({
      name: 'size',
      type: 'string',
      description: 'e.g. M, L, XL, OS, 32',
      validation: (r) => r.required(),
    }),
    defineField({
      name: 'condition',
      type: 'string',
      options: {list: CONDITIONS},
      initialValue: '9/10',
      validation: (r) => r.required(),
    }),
    defineField({
      name: 'measurements',
      title: 'Measurements (cm, laid flat)',
      type: 'object',
      options: {collapsible: true, collapsed: false, columns: 2},
      hidden: ({document}) => (document as Doc | undefined)?.category === 'hats',
      fields: [
        cm('chest', 'Pit to pit', 'Armpit to armpit', ['shirts']),
        cm('length', 'Length', 'Shirts: collar to hem · Shorts: waistband to hem', ['shirts', 'shorts']),
        cm('waist', 'Waist (flat)', 'Side to side across the waistband', ['shorts']),
        cm('inseam', 'Inseam', 'Crotch seam to hem', ['shorts']),
      ],
    }),
    defineField({
      name: 'description',
      type: 'text',
      rows: 3,
      description: 'Optional. Keep it short — mention any flaws.',
    }),
  ],
  orderings: [
    {title: 'Newest first', name: 'newest', by: [{field: '_createdAt', direction: 'desc'}]},
  ],
  preview: {
    select: {title: 'name', brand: 'brand', otherBrand: 'otherBrand', price: 'price', status: 'status', media: 'images.0'},
    prepare: ({title, brand, otherBrand, price, status, media}) => ({
      title: title || 'Untitled',
      subtitle: [
        status && status !== 'available' && String(status).toUpperCase(),
        brand === 'Other' ? otherBrand : brand,
        price != null && `₱${Number(price).toLocaleString('en-US')}`,
      ]
        .filter(Boolean)
        .join(' · '),
      media,
    }),
  },
})

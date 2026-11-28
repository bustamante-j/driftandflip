import {defineConfig} from 'sanity'
import {structureTool} from 'sanity/structure'
import {schemaTypes} from './schemaTypes'
import {projectId, dataset} from './env'

export default defineConfig({
  name: 'default',
  title: 'Drift&Flip',
  projectId,
  dataset,
  plugins: [
    structureTool({
      structure: (S) =>
        S.list()
          .title('Drift&Flip')
          .items([
            S.listItem()
              .title('Available')
              .child(S.documentList().title('Available').schemaType('product').filter('_type == "product" && (status == "available" || !defined(status))')),
            S.listItem()
              .title('Reserved')
              .child(S.documentList().title('Reserved').schemaType('product').filter('_type == "product" && status == "reserved"')),
            S.listItem()
              .title('Sold (Archive)')
              .child(S.documentList().title('Sold').schemaType('product').filter('_type == "product" && status == "sold"')),
            S.divider(),
            S.documentTypeListItem('product').title('All products'),
          ]),
    }),
  ],
  schema: {types: schemaTypes},
})

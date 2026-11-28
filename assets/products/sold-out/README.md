# Sold-out photos

Drop photos of **sold** pieces into the matching folder. They show up in the site's
**Archive** with a SOLD stamp. They can't be ordered.

```
sold-out/
├── shirts/
├── shorts/
└── hats/
```

## Name the file after the piece

```
Brand - Product name [Size].jpg
```

| File name | Shows as |
|---|---|
| `Chrome Hearts - Cemetery Cross Tee [L].jpg` | Chrome Hearts · Cemetery Cross Tee · size L |
| `Stussy - 8 Ball Tee.jpg` | Stüssy · 8 Ball Tee |
| `Chrome Hearts - Cemetery Cross Tee [L] (2).jpg` | 2nd photo of the same piece |

- The size `[L]` is optional.
- To add more photos of one piece, use the same name and add `(2)`, `(3)` and so on.
  The first photo is the cover. The second shows when someone hovers the card.
- JPG, PNG and WebP work. iPhone **HEIC** photos don't: export or share them as JPG first.
- Photos are shrunk and converted to WebP for the site, and their hidden location data is
  removed. The originals here stay as they are.

The photos go live when the site is next deployed.

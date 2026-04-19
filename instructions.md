# Book Page Update Instructions

Use these conventions whenever adding or updating books on this site.

## Content Source

- Book data comes from Amazon product pages.
- Pull the following fields from the listing:
  - Title
  - Subtitle (only if it exists)
  - Cover image
  - Description text (cleaned for site readability)
  - Book link (prefer a stable Amazon product URL like https://www.amazon.com/dp/ASIN)

## Cover Image Rules

- Use the larger/base version of the Amazon cover image when available.
- Avoid smaller thumbnail variants (for example URLs with size suffixes like `._SY466_`).
- Keep cover display size consistent with the existing cards:
  - `width="174"`
  - `height="261"`

## Layout And Style Rules

- Keep styling consistent with existing pages.
- Book cards should follow the same structure used on the main page:
  - Cover on the left (desktop) / stacked on mobile
  - Title as an `h2`
  - Subtitle as an `h4` only when the book has a real subtitle
  - Description in paragraph blocks below
- Keep a thin white border around all cover images:
  - `border: 1px solid white;`
- Keep text alignment behavior consistent with current responsive styles.

## Title Formatting

- Use the clean book title in the site card title.
- Do not append series names in the title unless that is intentionally part of the displayed title format for the site.
- If no subtitle exists, omit the subtitle line.

## Page Placement

- Main series books go on the main page (`index.html`).
- Other author books go on the secondary page (`other-books.html`).
- Keep navigation links between pages working after updates.

## Quick Checklist

- Confirm correct page placement (main vs other books).
- Confirm title/subtitle formatting rules are followed.
- Confirm cover image is the larger version and uses 174x261 display size.
- Confirm thin white border is visible around cover art.
- Confirm Amazon links open the intended book.
- Confirm page still looks consistent on mobile and desktop.

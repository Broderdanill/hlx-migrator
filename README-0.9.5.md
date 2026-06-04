# HLX Migrator 0.9.5

Changes:

- Adds server-side paging for object lists.
- Default page size is 500 rows.
- Adds Previous/Next and page-size controls in the workflow/object table.
- Object list API now supports `limit`, `offset`, `sort` and `direction`.
- Search is debounced and executed server-side instead of filtering thousands of rows in the browser.
- Cache still stores all objects; the UI only renders one page at a time for better performance.
- ConfigMap supports:

```yaml
ui:
  page_size: 500
  max_page_size: 2000
```

Build UI and backend if you want both API and frontend changes active.

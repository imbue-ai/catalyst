## 2024-05-30 - O(1) Lookups in React Render
**Learning:** React components containing loops over task.steps to render workflow visualizations (loops, parallels) are experiencing heavy render performance drops because O(N) array `.find` lookups inside loops lead to an O(N^2) or worse operation across deeply nested components.
**Action:** Created `getStepsMap` utility using `useMemo` at the component level to convert arrays to maps, changing lookup complexity from O(N) to O(1) during each render pass.

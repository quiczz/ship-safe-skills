# Framework recipes

Use the loading signal the code already has. Do not add new fetching logic just to show a skeleton. Show the skeleton on the **first load only**; on refetch keep the old data on screen.

## React (client fetching)

```tsx
const { data, isPending, error } = useQuery({ queryKey: ["projects"], queryFn: getProjects });

if (isPending) return <ProjectListSkeleton />;   // TanStack Query v5: isPending = no data yet
if (error) return <ErrorState error={error} />;
if (data.length === 0) return <EmptyState />;
return <ProjectList items={data} />;
```

- TanStack Query v4 and SWR: use `isLoading` for "no data yet". Do not use `isFetching` (it is true on refetch too).
- Redux Toolkit Query: `isLoading` (first load), not `isFetching`.
- Plain `useEffect` + `useState`: use the existing `loading` flag; make sure it starts `true` so there is no empty flash on first render.
- Suspense: put the boundary around the part that waits, not the whole page.
  `<Suspense fallback={<StatsSkeleton />}><Stats /></Suspense>`
- Fast data: wrap with `useDelayedLoading` (templates/useDelayedLoading.ts) or use `SkeletonRegion delayed`.

## Next.js App Router

- Route-level: add `loading.tsx` next to `page.tsx`. Next wraps the page in Suspense with it as the fallback and shows it instantly on navigation. See `templates/next-loading.tsx`.
- Part of a page: make the slow piece an async server component and wrap it:
  ```tsx
  export default function Page() {
    return (<>
      <Header />                                  {/* renders at once */}
      <Suspense fallback={<RevenueChartSkeleton />}>
        <RevenueChart />                          {/* async server component */}
      </Suspense>
    </>);
  }
  ```
- `loading.tsx` covers the page and its children, not the `layout.tsx` of the same segment. Put heavy fetching in the page, or add a nested `loading.tsx` one level down.
- A route with no dynamic data renders statically and needs no skeleton.
- Pages Router has no `loading.tsx`: use the client-side flag (`isLoading` from the data hook) or `router.events` for navigation.

## React Router v7 / Remix

- Navigation: `const navigation = useNavigation(); navigation.state === "loading"` for route transitions.
- Streaming: return un-awaited promises from the loader and render
  `<React.Suspense fallback={<ListSkeleton />}><Await resolve={data.items}>{(items) => <List items={items} />}</Await></React.Suspense>`.
- Initial route skeleton: export `HydrateFallback` from the route module.

## Vue 3 / Nuxt

```vue
<script setup>
const { data, status } = await useAsyncData("projects", () => $fetch("/api/projects"), { lazy: true });
</script>
<template>
  <ProjectListSkeleton v-if="status === 'pending'" />
  <ErrorState v-else-if="status === 'error'" />
  <ProjectList v-else :items="data" />
</template>
```

- `lazy: true` (or `useLazyAsyncData`) lets navigation happen immediately so the skeleton can show; without it Nuxt waits for the data before showing the page.
- Plain Vue: `v-if="loading"` on the existing flag. `<Suspense>` with an async `setup` works but is still marked experimental.
- Overlay mode: `:data-loading="loading"` on the container and `class="sk-o"` on elements.

## SvelteKit / Svelte

```svelte
{#await data.items}
  <ListSkeleton />
{:then items}
  <List {items} />
{:catch}
  <ErrorState />
{/await}
```

- In `+page.ts` / `+page.server.ts`, return the promise un-awaited (nested inside the returned object) to stream it, so the page renders first.
- Client-only flags: `{#if loading}<ListSkeleton />{:else}...{/if}`.

## Angular

- Data from HTTP / signals: `@if (loading()) { <app-list-skeleton /> } @else { <app-list [items]="items()" /> }`.
- `@defer` placeholders are for lazy-loaded **code**, not API data:
  ```html
  @defer (on viewport) { <app-heavy-chart /> }
  @placeholder (minimum 500ms) { <app-chart-skeleton /> }
  @loading (after 100ms; minimum 1s) { <app-chart-skeleton /> }
  ```
  `after` / `minimum` are Angular's built-in anti-flash timing.

## Plain HTML / any server-rendered site

1. Add `templates/skeleton.css`.
2. Overlay mode: server renders the real markup with `data-loading="true"` on the container; JS sets it to `false` when data arrives.
3. Mirror mode: render skeleton markup in the container, replace its `innerHTML` with real content, and remove `aria-busy`.
4. HTMX: `hx-indicator` can point at a skeleton block, or use `hx-swap` with a skeleton as the initial content (`hx-trigger="load"`).

## React Native

No CSS, so build blocks as `View`s with the real sizes and animate opacity (about 0.4 to 1) with `Animated` and `useNativeDriver: true`. Check `AccessibilityInfo.isReduceMotionEnabled()` and skip the animation if true. Mark the list `accessibilityState={{ busy: true }}`. FlatList: render N placeholder items when `isLoading`; keep `getItemLayout` or fixed row heights so there is no jump.

## Flutter

The `skeletonizer` package wraps existing widgets and paints them as bones, so you keep one widget tree:
```dart
Skeletonizer(
  enabled: isLoading,
  child: ProjectList(items: isLoading ? fakeItems : items),   // fakeItems: dummy models of similar length
)
```
Use `Skeleton.ignore` / `Skeleton.keep` on parts that should stay as they are. Add it with `flutter pub add skeletonizer`. Without the package: `FutureBuilder` / `AsyncValue.when(loading: ...)` (Riverpod) returning hand-built bone widgets of the real size. Respect `MediaQuery.disableAnimationsOf(context)`.

## SwiftUI

```swift
List(items) { ProjectRow(project: $0) }
    .redacted(reason: isLoading ? .placeholder : [])
```
Use placeholder model values of similar length while loading, and `.unredacted()` on views that must stay readable. Add a shimmer with a repeating gradient mask only if `@Environment(\.accessibilityReduceMotion)` is false.

## Android (Compose)

No built-in. Build `Box` blocks with the real sizes and animate alpha with `rememberInfiniteTransition`. Respect the system animation scale (`Settings.Global.ANIMATOR_DURATION_SCALE == 0`).

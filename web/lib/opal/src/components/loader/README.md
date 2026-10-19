# Loader

**Import:** `import { OnyxLoader } from "@opal/components";`

The branded compass mark: the ring and the ring with its needle crossfade while rotating a full turn on a 2s loop. It takes a `color` token (default `border-02`) and holds still under `prefers-reduced-motion`.

```tsx
<OnyxLoader />
<OnyxLoader size={24} color="text-04" />
```

Props: `size` (px, default 64 with a ~2.5px stroke that scales), `color` (`LoaderColor`, default `border-02`). The mark geometry matches the compass mark in `@opal/logos`. The stroke is defined locally so its weight can be tuned.

The loaders for app use (`PageLoader`, `IconLoader`, `CardLoader`, `LineLoader`, `TextLoader`) live in `@opal/loaders`.

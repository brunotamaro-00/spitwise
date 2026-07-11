---
name: icons-system
description: Rules for icon usage in the Trip Europa app. Replace emojis with Lucide icons, enforce consistent sizing and style, and keep country flags as unicode/flag-icons.
---

You are enforcing the icon system for this Next.js travel app. Apply these rules when generating new UI or auditing existing components.

## Core Rule

**No emojis as UI chrome.** Emojis are only allowed for country flags (see below). All other iconography must use Lucide React.

## Library: Lucide React

Already available via shadcn/ui. Import pattern:

```tsx
import { MapPin, Calendar, Wallet, ChevronRight } from 'lucide-react'
```

Browse icons at: lucide.dev

## Icon Style Rules

| Property | Value | Rationale |
|---|---|---|
| `strokeWidth` | `1.5` | Feels refined, not heavy |
| Size — inline/label | `16` (w-4 h-4) | Matches text baseline |
| Size — standalone/action | `20` (w-5 h-5) | Comfortable tap target |
| Size — hero/empty state | `32–48` (w-8–w-12 h-8–w-12) | Visible at a glance |
| Color | `currentColor` | Inherits from text, never hardcoded |
| `aria-hidden` | `true` on decorative icons | Screen readers skip them |
| `aria-label` | Required on icon-only buttons | e.g., `<button aria-label="Close">` |

## Common Replacements for This App

| Emoji | Replace with | Lucide icon name |
|---|---|---|
| 📍 🗺️ | Location/stop | `MapPin` |
| 📅 🗓️ | Date/schedule | `Calendar` |
| 💰 💵 | Budget/currency | `Wallet`, `Banknote` |
| 🌤️ ☀️ | Weather | `Sun`, `Cloud`, `CloudRain` |
| 📝 ✏️ | Notes/edit | `FileText`, `Pencil` |
| 🏛️ 🎭 | Points of interest | `Landmark`, `Ticket` |
| ✈️ | Flight/travel | `Plane` |
| 🏨 | Accommodation | `BedDouble` |
| 🍽️ | Food/restaurant | `UtensilsCrossed` |
| ⬅️ → | Navigation | `ChevronLeft`, `ChevronRight` |
| ✓ ✅ | Done/checked | `Check`, `CheckCircle2` |
| ✕ ❌ | Close/remove | `X` |
| ➕ | Add | `Plus` |
| ⚙️ | Settings | `Settings` |
| 🔍 | Search | `Search` |
| 👤 | User/profile | `User` |
| ⚠️ | Warning | `AlertTriangle` |
| ℹ️ | Info | `Info` |

## Country Flags

Country flags are the **only allowed emoji** in this app. Use standard unicode flag emoji:

```tsx
// Good — flags only
<span>🇮🇹 Italy</span>
<span>🇫🇷 France</span>

// Also good for better rendering — flag-icons CSS library
<span className="fi fi-it" /> Italy
```

If using `flag-icons`, install with: `npm install flag-icons` and import the CSS in `layout.tsx`.

## Component Pattern

Wrap commonly-used icons in typed components to enforce consistency:

```tsx
import { LucideIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

interface IconProps {
  icon: LucideIcon
  size?: 'sm' | 'md' | 'lg'
  className?: string
  label?: string  // required for standalone/interactive icons
}

const sizes = { sm: 'w-4 h-4', md: 'w-5 h-5', lg: 'w-8 h-8' }

export function Icon({ icon: LucideIcon, size = 'md', className, label }: IconProps) {
  return (
    <LucideIcon
      className={cn(sizes[size], className)}
      strokeWidth={1.5}
      aria-hidden={!label}
      aria-label={label}
    />
  )
}
```

## When Auditing Existing Code

1. Find all emoji characters in `.tsx` files: `grep -r "[^\x00-\x7F]" src/`
2. For each emoji: determine if it's a flag (keep) or UI chrome (replace)
3. Apply the replacement table above
4. Ensure every icon-only interactive element has an `aria-label`

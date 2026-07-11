import {
  BedDouble,
  Bus,
  type LucideIcon,
  ShoppingBag,
  Tag,
  Ticket,
  UtensilsCrossed,
  Wine,
} from "lucide-react";

/** Nombre de categoría (catálogo backend) -> ícono Lucide. Fallback: Tag. */
const MAP: Record<string, LucideIcon> = {
  Alojamiento: BedDouble,
  Comida: UtensilsCrossed,
  Transporte: Bus,
  Actividades: Ticket,
  Compras: ShoppingBag,
  "Bebidas/Salidas": Wine,
  Otros: Tag,
};

export function categoryIcon(name: string | null | undefined): LucideIcon {
  return (name && MAP[name]) || Tag;
}

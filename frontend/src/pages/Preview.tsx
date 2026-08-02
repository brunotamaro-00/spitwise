import { Coffee, Landmark, Receipt, Utensils, Wallet } from "lucide-react";
import { useState } from "react";

import BandBadge from "@/components/BandBadge";
import DeltaBadge from "@/components/DeltaBadge";
import Badge, { CountBadge } from "@/components/ui/Badge";
import { PageTitle, SpitDivider, Wordmark } from "@/components/ui/Brand";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import ConfirmDialog from "@/components/ui/ConfirmDialog";
import EmptyState from "@/components/ui/EmptyState";
import ErrorState from "@/components/ui/ErrorState";
import { Field, Input, Select } from "@/components/ui/Field";
import Kpi from "@/components/ui/Kpi";
import SectionHeader from "@/components/ui/SectionHeader";
import Skeleton from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";

/** Kitchen-sink dev-only (`/preview`): cada primitivo con TODOS sus estados.
 *  Es la herramienta de verificación visual del sistema — todo primitivo nuevo
 *  se agrega acá en el mismo commit que lo crea (ver .interface-design/system.md).
 *  No se registra en producción: la ruta solo existe bajo import.meta.env.DEV. */

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="flex items-center gap-2 text-sm font-bold text-ink">
        {title}
        <SpitDivider />
      </h2>
      {children}
    </section>
  );
}

export default function Preview() {
  const toast = useToast();
  const [confirming, setConfirming] = useState(false);

  return (
    <div className="mx-auto flex max-w-lg flex-col gap-8 p-4 pb-24 lg:max-w-3xl">
      <PageTitle>Preview</PageTitle>

      <Section title="Marca">
        <Card className="flex flex-col items-start gap-3 p-5">
          <Wordmark className="text-wordmark" />
          <span className="espresso-panel rounded-xl px-4 py-2">
            <Wordmark tone="dark" className="text-wordmark" />
          </span>
        </Card>
      </Section>

      <Section title="Button — variantes × estados">
        <Card className="flex flex-col gap-3 p-5">
          {(["primary", "secondary", "ghost", "danger"] as const).map((v) => (
            <div key={v} className="flex flex-wrap items-center gap-2">
              <Button variant={v}>{v}</Button>
              <Button variant={v} size="sm">sm</Button>
              <Button variant={v} disabled>disabled</Button>
            </div>
          ))}
        </Card>
      </Section>

      <Section title="Badge — tonos × tamaños">
        <Card className="flex flex-col gap-3 p-5">
          <div className="flex flex-wrap items-center gap-2">
            <Badge>neutral</Badge>
            <Badge tone="teal">teal</Badge>
            <Badge tone="amber">amber</Badge>
            <Badge tone="brick">brick</Badge>
            <Badge tone="amber" size="sm" caps>Por confirmar</Badge>
            <Badge tone="teal" size="sm" caps>CB 5%</Badge>
            <Badge tone="brick" size="sm" caps>hoy</Badge>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <BandBadge position="under" edgeDeltaPct={null} />
            <BandBadge position="in" edgeDeltaPct={null} />
            <BandBadge position="over" edgeDeltaPct={9} />
            <DeltaBadge pct={40} />
            <DeltaBadge pct={-22} compact />
            <DeltaBadge pct={4} />
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <CountBadge count={4} aria-label="4 por confirmar" />
            <CountBadge count={12} size="sm" aria-label="12 por confirmar" />
            <CountBadge count={3} tone="brick" size="sm" aria-label="3 filtros activos" />
          </div>
        </Card>
      </Section>

      <Section title="SectionHeader — variantes">
        <Card className="flex flex-col gap-4 p-5">
          <SectionHeader>Título simple</SectionHeader>
          <SectionHeader icon={Wallet}>Con ícono brick</SectionHeader>
          <SectionHeader icon={Landmark} iconTone="teal" hint="real vs plan · por persona">
            Ícono teal + hint
          </SectionHeader>
          <SectionHeader action={<Button variant="ghost" size="sm">Ver todos</Button>}>
            Con acción
          </SectionHeader>
          <SectionHeader quiet hint="últimos 30 días">Quiet (título de chart)</SectionHeader>
        </Card>
      </Section>

      <Section title="Kpi — tints">
        <div className="grid grid-cols-2 gap-3">
          <Kpi icon={Wallet} tint="brick" label="Total" value="USD 9.447" />
          <Kpi icon={Utensils} tint="blue" label="Comida" value="USD 626,74" />
          <Kpi icon={Landmark} tint="teal" label="Actividades" value="USD 561,88" badge={<DeltaBadge pct={-12} compact />} />
          <Kpi icon={Coffee} tint="amber" label="Cafetería" value="USD 305" />
        </div>
      </Section>

      <Section title="Formulario">
        <Card className="flex flex-col gap-4 p-5">
          <Field label="Descripción" hint="opcional">
            <Input placeholder="Cena en el mercado" />
          </Field>
          <Field label="Categoría">
            <Select defaultValue="comida">
              <option value="comida">Comida</option>
              <option value="transporte">Transporte</option>
            </Select>
          </Field>
        </Card>
      </Section>

      <Section title="Feedback">
        <Card className="flex flex-wrap items-center gap-2 p-5">
          <Button variant="secondary" size="sm" onClick={() => toast("success", "Gasto guardado")}>
            Toast éxito
          </Button>
          <Button variant="secondary" size="sm" onClick={() => toast("error", "No se pudo confirmar. Probá de nuevo.")}>
            Toast error
          </Button>
          <Button variant="secondary" size="sm" onClick={() => setConfirming(true)}>
            ConfirmDialog
          </Button>
        </Card>
      </Section>

      <Section title="Loading / vacío / error">
        <Card className="flex flex-col gap-3 p-5">
          <Skeleton className="h-6 w-1/2" />
          <Skeleton className="h-24 w-full" />
        </Card>
        <Card>
          <EmptyState
            icon={Receipt}
            title="Nada por acá"
            description="Cuando cargues un gasto lo vas a ver en esta lista."
            action={<Button size="sm">Agregar gasto</Button>}
          />
        </Card>
        <ErrorState onRetry={() => toast("success", "Reintentado")} />
      </Section>

      {confirming && (
        <ConfirmDialog
          title="¿Borrar el gasto?"
          message="Esta acción no se puede deshacer."
          onConfirm={() => setConfirming(false)}
          onClose={() => setConfirming(false)}
        />
      )}
    </div>
  );
}

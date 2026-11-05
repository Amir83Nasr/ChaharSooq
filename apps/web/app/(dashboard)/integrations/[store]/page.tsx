import { notFound } from "next/navigation"

import { AutoStoreView } from "./_components/auto-store-view"
import { GroupStoreView } from "./_components/group-store-view"
import { STORES, isAutoStoreKey, isStoreKey } from "../_components/store-config"

export default async function IntegrationPage({
  params,
}: {
  params: Promise<{ store: string }>
}) {
  const { store } = await params
  if (!isStoreKey(store)) notFound()
  const integration = STORES[store]

  if (isAutoStoreKey(store)) {
    return (
      <AutoStoreView
        store={store}
        storeName={integration.name}
        description={integration.description}
      />
    )
  }

  return (
    <GroupStoreView
      topGroup={integration.topGroup}
      storeName={integration.name}
      description={integration.description}
    />
  )
}

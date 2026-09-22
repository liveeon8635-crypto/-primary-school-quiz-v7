"""Read-only V1 teaching-cycle endpoint backed by existing program facts."""

from __future__ import annotations

from types import ModuleType
from fastapi import APIRouter, Depends

from changying.domain.teaching_cycle_read_model import teaching_cycle_rows


def install_v1_teaching_cycle_routes(implementation: ModuleType) -> None:
    app=implementation.app
    if getattr(app.state,"v1_teaching_cycle_routes_installed",False):
        return

    router = APIRouter()

    @router.get("/v1/teaching-cycles", include_in_schema=False)
    def teaching_cycles(user=Depends(implementation.current_user),db=Depends(implementation.get_db)):
        implementation.need(user,"teacher","admin")
        rows=teaching_cycle_rows(implementation,db,int(user.school_id))
        return {
            "scope":"existing-teaching-program-facts",
            "storageNeutral":True,
            "cycles":rows,
            "count":len(rows),
        }

    app.include_router(router)
    app.state.v1_teaching_cycle_routes_installed=True


__all__=["install_v1_teaching_cycle_routes"]

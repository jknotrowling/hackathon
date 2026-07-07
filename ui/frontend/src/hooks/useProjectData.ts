import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '../api/client';
import type { FlightCreate, FlightUpdate, RegionCreate } from '../types';

export function useProjects() {
  return useQuery({
    queryKey: ['projects'],
    queryFn: api.getProjects,
  });
}

export function useProject(projectId: number | null) {
  return useQuery({
    queryKey: ['projects', projectId],
    queryFn: () => api.getProject(projectId!),
    enabled: projectId !== null,
  });
}

export function useBoundary(projectId: number | null) {
  return useQuery({
    queryKey: ['projects', projectId, 'boundary'],
    queryFn: () => api.getBoundary(projectId!),
    enabled: projectId !== null,
  });
}

export function useRegions(projectId: number | null) {
  return useQuery({
    queryKey: ['projects', projectId, 'regions'],
    queryFn: () => api.getRegions(projectId!),
    enabled: projectId !== null,
  });
}

export function useRegionMutations(projectId: number | null) {
  const queryClient = useQueryClient();

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['projects', projectId, 'regions'] });

  const create = useMutation({
    mutationFn: (payload: RegionCreate) => api.createRegion(projectId!, payload),
    onSuccess: invalidate,
  });

  const update = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Partial<RegionCreate> }) =>
      api.updateRegion(id, payload),
    onSuccess: invalidate,
  });

  const remove = useMutation({
    mutationFn: (id: number) => api.deleteRegion(id),
    onSuccess: invalidate,
  });

  return { create, update, remove };
}

export function useStockpiles(projectId: number | null) {
  return useQuery({
    queryKey: ['projects', projectId, 'stockpiles'],
    queryFn: () => api.getStockpiles(projectId!),
    enabled: projectId !== null,
  });
}

export function useSurveys(projectId: number | null) {
  return useQuery({
    queryKey: ['projects', projectId, 'surveys'],
    queryFn: () => api.getSurveys(projectId!),
    enabled: projectId !== null,
  });
}

export function useFlights(projectId: number | null) {
  return useQuery({
    queryKey: ['projects', projectId, 'flights'],
    queryFn: () => api.getFlights(projectId!),
    enabled: projectId !== null,
  });
}

export function useFlightMutations(projectId: number | null) {
  const queryClient = useQueryClient();

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['projects', projectId, 'flights'] });

  const create = useMutation({
    mutationFn: (payload: FlightCreate) => api.createFlight(projectId!, payload),
    onSuccess: invalidate,
  });

  const update = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: FlightUpdate }) =>
      api.updateFlight(id, payload),
    onSuccess: invalidate,
  });

  const remove = useMutation({
    mutationFn: (id: number) => api.deleteFlight(id),
    onSuccess: invalidate,
  });

  const planMapping = useMutation({
    mutationFn: (regionId: number) => api.planMappingFlights(regionId),
    onSuccess: invalidate,
  });

  return { create, update, remove, planMapping };
}

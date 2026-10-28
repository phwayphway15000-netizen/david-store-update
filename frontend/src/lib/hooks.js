import { useQuery } from "@tanstack/react-query";
import { api } from "./api";

const get = (url) => () => api.get(url).then((r) => r.data);

export const useSettings = () => useQuery({ queryKey: ["settings"], queryFn: get("/settings/public") });
export const useCategories = () => useQuery({ queryKey: ["categories"], queryFn: get("/categories") });
export const useBrands = () => useQuery({ queryKey: ["brands"], queryFn: get("/brands") });
export const usePromotions = () => useQuery({ queryKey: ["promotions"], queryFn: get("/promotions") });

import { authHandlers } from './auth';
import { licensesHandlers } from './licenses';
import { dashboardHandlers } from './dashboard';

export const handlers = [...authHandlers, ...licensesHandlers, ...dashboardHandlers];

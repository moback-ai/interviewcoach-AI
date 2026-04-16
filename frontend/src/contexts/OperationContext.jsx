import { createContext, useContext, useMemo, useState } from 'react';

const OperationContext = createContext(undefined);

export const OperationProvider = ({ children }) => {
  const [isOperationInProgress, setIsOperationInProgress] = useState(false);

  const value = useMemo(() => ({
    isOperationInProgress,
    setIsOperationInProgress,
  }), [isOperationInProgress]);

  return (
    <OperationContext.Provider value={value}>
      {children}
    </OperationContext.Provider>
  );
};

export const useOperation = () => {
  const context = useContext(OperationContext);
  if (context === undefined) {
    throw new Error('useOperation must be used within OperationProvider');
  }
  return context;
};
